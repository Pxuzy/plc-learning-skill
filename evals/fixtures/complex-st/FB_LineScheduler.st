(* ============================================================
   FB_LineScheduler.st —— 整线主调度（#14 的顶层）
   平台：Omron NJ/NX（Sysmac Studio，IEC 61131-3 ST）
   性质：虚构测试夹具，全部名称与逻辑均为合成，无现场地址、无用户工程源码。负责工位使能、缓存道仲裁、节拍同步、
         故障分级与急停恢复，不直接驱动任何输出。
   设计要点：
     1) 每个工位有独立的使能链：整线放行 AND 本工位健康 AND 下游不堵；
     2) 下游堵时按“先堵后饿”顺序回收上游使能，防止工位把料推死；
     3) 急停分三级：安全停（全线断使能）、可自恢复、需人工；
     4) 恢复按由后向前的顺序逐个放行，任一工位未复位则全线保持暂停；
     5) 所有等待都有上限，超限落诊断而不是无限等。
   ============================================================ *)

FUNCTION_BLOCK FB_LineScheduler
VAR_INPUT
    nStationCount : INT;      (* 工位数，1..8，运行期不变 *)
    xLineStart    : BOOL;     (* TRUE 全线启动请求 *)
    xLineStop     : BOOL;     (* TRUE 全线停止请求，按顺序收尾 *)
    xEStop        : BOOL;     (* TRUE 急停生效，来自安全回路 *)
    xResetAll     : BOOL;     (* TRUE 全线复位请求 *)
    aeStationBusy : ARRAY[0..7] OF BOOL;   (* 各工位占用 *)
    aeStationFault: ARRAY[0..7] OF BOOL;   (* 各工位故障 *)
    aeStationReady: ARRAY[0..7] OF BOOL;   (* 各工位就绪 *)
    anStationCycle: ARRAY[0..7] OF INT;    (* 各工位最近节拍毫秒 *)
    xPartOutPulse : BOOL;     (* 末端出件脉冲，上升沿计一件 *)
    xBufferFull   : BOOL;     (* 缓存道满 *)
    xBufferEmpty  : BOOL;     (* 缓存道空 *)
END_VAR

VAR_OUTPUT
    aeEnable      : ARRAY[0..7] OF BOOL;   (* 各工位使能，直连工位 xEnable *)
    xLineRunning  : BOOL;     (* TRUE 全线运行中 *)
    xLinePaused   : BOOL;     (* TRUE 全线暂停，等待恢复 *)
    nLineState    : INT;      (* 整线状态号 *)
    nFaultLevel   : INT;      (* 故障分级：0 无，1 自恢复，2 人工，3 安全停 *)
    nFaultStation : INT;      (* 首故障工位号，0 无 *)
    nDiagCode     : WORD;     (* 诊断码，0 正常 *)
    nBottleneck   : INT;      (* 节拍最长工位号，0 未知 *)
    nTactMS       : INT;      (* 全线节拍，取最慢工位 *)
    nThroughput   : UDINT;   (* 累计完成件数 *)
    xAllReady     : BOOL;     (* TRUE 全部工位就绪 *)
    xDeadlockWarn : BOOL;     (* TRUE 检测到潜在互等，已强制回收 *)
END_VAR

VAR
    (* 整线状态号，与 nLineState 同源 *)
    nStIdle       : INT := 0;
    nStStarting   : INT := 10;
    nStRunning    : INT := 20;
    nStDraining   : INT := 30;
    nStPaused     : INT := 40;
    nStFaulted    : INT := 50;
    nStSafeStop   : INT := 60;

    nStatePre     : INT;      (* 上一扫描整线状态 *)
    nStationMax   : INT;      (* 工位数钳位结果 *)
    i             : INT;      (* 工位扫描下标 *)
    nFaultCount   : INT;      (* 本扫描故障工位数 *)
    nFirstFault   : INT;      (* 本扫描首个故障工位 *)
    nSlowest      : INT;      (* 节拍最长工位 *)
    nSlowestMS    : INT;      (* 节拍最长值 *)
    nSumMS        : INT;      (* 节拍合计，仅用于均值参考 *)
    xUpstreamOk   : BOOL;     (* TRUE 上游链路当前都健康 *)
    xDownBlocked  : BOOL;     (* TRUE 下游存在阻塞 *)
    xAnyBusy      : BOOL;     (* TRUE 还有工位在忙 *)
    xAllIdle      : BOOL;     (* TRUE 全部工位空闲 *)

    rTrigEStop    : R_TRIG;   (* 急停上升沿 *)
    rTrigReset    : R_TRIG;   (* 复位上升沿 *)
    rTrigStart    : R_TRIG;   (* 启动上升沿 *)
    rTrigStop     : R_TRIG;   (* 停止上升沿 *)
    rTrigPartOut  : R_TRIG;   (* 出件脉冲上升沿 *)

    tonStart      : TON;      (* 启动超时：全员就绪等太久就报警 *)
    tonRecover    : TON;      (* 恢复超时：恢复阶段卡住则升级为人工 *)
    tonDeadlock   : TON;      (* 互等检测：全忙且缓存满持续过久 *)

    xEStopNow     : BOOL;     (* 本扫描急停有效 *)
    nRecoverIdx   : INT;      (* 恢复放行游标，由后向前 *)
    xRecovering   : BOOL;     (* TRUE 正在逐级放行 *)
    nCycleBuf     : ARRAY[0..7] OF INT;  (* 节拍滑动缓冲，仅保留最近一次 *)
    xDeadlock     : BOOL;     (* TRUE 判定互等 *)
    nDeadlockCnt  : UINT;     (* 互等判定次数 *)
END_VAR

METHOD PRIVATE ClampStations : INT
IF nStationCount < 1 THEN
    ClampStations := 1;
ELSIF nStationCount > 8 THEN
    ClampStations := 8;
ELSE
    ClampStations := nStationCount;
END_IF;
END_METHOD

METHOD PRIVATE ScanStations : BOOL
(* 汇总工位健康：故障数、首故障、节拍瓶颈 *)
VAR
    m : INT;
END_VAR
nFaultCount := 0;
nFirstFault := 0;
nSlowest := 0;
nSlowestMS := -1;
nSumMS := 0;
xAnyBusy := FALSE;
xAllIdle := TRUE;

FOR m := 0 TO nStationMax - 1 DO
    IF aeStationFault[m] THEN
        nFaultCount := nFaultCount + 1;
        IF nFirstFault = 0 THEN
            nFirstFault := m + 1;            (* 工位号按 1 起对外 *)
        END_IF;
    END_IF;
    IF aeStationBusy[m] THEN
        xAnyBusy := TRUE;
        xAllIdle := FALSE;
    END_IF;
    IF anStationCycle[m] > nSlowestMS THEN
        nSlowestMS := anStationCycle[m];
        nSlowest := m + 1;
    END_IF;
    nSumMS := nSumMS + anStationCycle[m];
END_FOR;

nBottleneck := nSlowest;
IF nSlowestMS < 0 THEN
    nTactMS := 0;                            (* 全都没节拍数据 *)
ELSE
    nTactMS := nSlowestMS;                   (* 整线节拍取瓶颈工位 *)
END_IF;
ScanStations := TRUE;
END_METHOD

METHOD PRIVATE ComputeDeadlock : BOOL
(* 互等判定：全部工位都忙、缓存满、且持续超过限时，说明谁也动不了 *)
VAR
    m : INT;
END_VAR
xDownBlocked := xBufferFull;
xUpstreamOk := TRUE;
FOR m := 0 TO nStationMax - 1 DO
    IF aeStationFault[m] THEN
        xUpstreamOk := FALSE;                (* 有故障就谈不上上游健康 *)
    END_IF;
END_FOR;

IF xAnyBusy AND xBufferFull AND nFaultCount = 0 THEN
    xDeadlock := TRUE;
ELSE
    xDeadlock := FALSE;
END_IF;
ComputeDeadlock := xDeadlock;
END_METHOD

METHOD PRIVATE BuildEnable : BOOL
(* 使能链：由后端向前端逐级判断，下游不健康就掐上游 *)
VAR
    m       : INT;
    xChain  : BOOL;
END_VAR
xChain := xLineRunning AND NOT xEStopNow AND nFaultLevel < nSevManual;

FOR m := nStationMax - 1 TO 0 BY -1 DO
    (* 逆序：从最后一道工序往回流，保证下游先放行 *)
    IF NOT xChain THEN
        aeEnable[m] := FALSE;
    ELSIF aeStationFault[m] THEN
        aeEnable[m] := FALSE;                (* 自身故障，停自己 *)
    ELSIF xRecovering AND m >= nRecoverIdx THEN
        aeEnable[m] := TRUE;                 (* 恢复阶段：已放行的后端保持使能 *)
    ELSIF xRecovering THEN
        aeEnable[m] := FALSE;                (* 恢复阶段：前端一律压住 *)
        xChain := FALSE;
    ELSE
        aeEnable[m] := TRUE;
    END_IF;
END_FOR;
BuildEnable := TRUE;
END_METHOD

(* ---------- 主扫描 ---------- *)

IF nStationMax = 0 THEN
    nStationMax := ClampStations();          (* 首扫描锁定工位数 *)
END_IF;

rTrigEStop(CLK := xEStop);
rTrigReset(CLK := xResetAll);
rTrigStart(CLK := xLineStart);
rTrigStop(CLK := xLineStop);

xEStopNow := xEStop;
ScanStations();

(* 故障分级：安全停 > 人工 > 自恢复 *)
IF xEStopNow THEN
    nFaultLevel := nSevSafeStop;
ELSIF nFaultCount > 0 THEN
    IF nFaultCount >= 2 THEN
        nFaultLevel := nSevManual;           (* 多点故障需人工确认 *)
    ELSE
        nFaultLevel := nSevRecover;          (* 单点故障允许自恢复 *)
    END_IF;
    nFaultStation := nFirstFault;
ELSE
    nFaultLevel := nSevNone;
    nFaultStation := 0;
END_IF;

(* 急停：无条件断全部使能并进入安全停，恢复必须走复位 *)
IF rTrigEStop.Q THEN
    nLineState := nStSafeStop;
    xLineRunning := FALSE;
    xLinePaused := FALSE;
    xRecovering := FALSE;
    nRecoverIdx := nStationMax;
    tonRecover(IN := FALSE, PT := T#0MS);
    tonStart(IN := FALSE, PT := T#0MS);
    nDiagCode := 16#0201;                    (* 急停生效 *)
END_IF;

(* 停止请求：不硬断，等工位把手上的活干完 *)
IF rTrigStop.Q AND nLineState = nStRunning THEN
    nLineState := nStDraining;
    nDiagCode := 16#0202;                    (* 收尾中 *)
END_IF;

(* 启动请求：只在空闲或收尾完成时接受 *)
IF rTrigStart.Q THEN
    CASE nLineState OF
        nStIdle, nStPaused:
            nLineState := nStStarting;
            tonStart(IN := TRUE, PT := T#3000MS);
            nDiagCode := 0;
        nStSafeStop:
            nDiagCode := 16#0203;            (* 安全停后必须先复位 *)
    ELSE
        ;
    END_CASE;
END_IF;

(* 复位：清故障分级与恢复游标，回到空闲 *)
IF rTrigReset.Q AND NOT xEStopNow THEN
    nLineState := nStIdle;
    xLineRunning := FALSE;
    xLinePaused := FALSE;
    xRecovering := FALSE;
    nRecoverIdx := nStationMax;
    nDiagCode := 0;
    tonRecover(IN := FALSE, PT := T#0MS);
    tonDeadlock(IN := FALSE, PT := T#0MS);
END_IF;

(* 互等检测：全忙 + 缓存满且超时，强制解除，避免整线停死 *)
ComputeDeadlock();
tonDeadlock(IN := xDeadlock, PT := T#5000MS);
xDeadlockWarn := tonDeadlock.Q;
IF tonDeadlock.Q THEN
    nDeadlockCnt := nDeadlockCnt + 1;
    IF nDeadlockCnt = 1 THEN
        nDiagCode := 16#0204;                (* 检出互等，已强制回收 *)
    END_IF;
    IF nLineState = nStRunning THEN
        nLineState := nStPaused;             (* 暂停等人工介入，不自动重启 *)
        xLinePaused := TRUE;
    END_IF;
END_IF;

(* 启动阶段：等全员就绪，超时则退回空闲并报警 *)
CASE nLineState OF
    nStStarting:
        xAllReady := TRUE;
        FOR i := 0 TO nStationMax - 1 DO
            IF NOT aeStationReady[i] THEN
                xAllReady := FALSE;          (* 任一未就绪就继续等 *)
            END_IF;
        END_FOR;
        IF nFaultCount > 0 THEN
            nLineState := nStPaused;         (* 启动期出故障，先暂停 *)
            nDiagCode := 16#0205;
        ELSIF xAllReady THEN
            nLineState := nStRunning;
            xLineRunning := TRUE;
            xLinePaused := FALSE;
            tonStart(IN := FALSE, PT := T#0MS);
            nDiagCode := 0;
        ELSIF tonStart.Q THEN
            nLineState := nStIdle;
            nDiagCode := 16#0206;            (* 启动超时：就绪条件长期不满足 *)
        END_IF;
    nStDraining:
        IF xAllIdle THEN
            nLineState := nStIdle;           (* 全部干完，回到空闲 *)
            xLineRunning := FALSE;
            nDiagCode := 0;
        END_IF;
    nStRunning:
        IF nFaultLevel = nSevManual THEN
            nLineState := nStPaused;         (* 多点故障：整线暂停 *)
            xLinePaused := TRUE;
            nDiagCode := 16#0207;
        ELSIF nFaultLevel = nSevRecover AND nFaultCount > 0 THEN
            ;                                (* 单点故障：只掐该工位，其余继续 *)
        END_IF;
    ELSE
        ;
END_CASE;

(* 自恢复：单点故障消失后把使能链重新放行 *)
IF nLineState = nStRunning AND nFaultLevel = nSevNone AND xRecovering THEN
    nRecoverIdx := nRecoverIdx - 1;
    IF nRecoverIdx < 0 THEN
        xRecovering := FALSE;
        nRecoverIdx := 0;
        tonRecover(IN := FALSE, PT := T#0MS);
    END_IF;
END_IF;

(* 需要恢复的判定：暂停后恢复运行，从最后一台往前逐台放行 *)
IF nLineState = nStRunning AND nStatePre = nStPaused THEN
    xRecovering := TRUE;
    nRecoverIdx := nStationMax;              (* 从最末端开始放行 *)
    tonRecover(IN := TRUE, PT := T#10000MS);
END_IF;
IF tonRecover.Q THEN
    nDiagCode := 16#0208;                    (* 恢复超时：逐级放行卡住 *)
    nFaultLevel := nSevManual;
    xRecovering := FALSE;
    tonRecover(IN := FALSE, PT := T#0MS);
END_IF;

BuildEnable();

(* 对外汇总 *)
xLinePaused := nLineState = nStPaused;
xLineRunning := xLineRunning AND nLineState = nStRunning;

(* 产量计数：按末端出件脉冲的上升沿计，不用扫描周期冒充件数 *)
rTrigPartOut(CLK := xPartOutPulse);
IF rTrigPartOut.Q AND nLineState = nStRunning THEN
    nThroughput := nThroughput + 1;
END_IF;

nStatePre := nLineState;
