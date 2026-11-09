(* ============================================================
   FB_StationCell.st —— 单工位控制块（#14 整线框架的工位层）
   平台：Omron NJ/NX（Sysmac Studio，IEC 61131-3 ST）
   性质：虚构测试夹具，全部名称与逻辑均为合成，无现场地址、无用户工程源码。工位内部用 #9 状态机引擎驱动，不写死 IF 链条。
   职责边界：
     1) 只认“上游来料 / 下游可收 / 本工位就绪”三类条件，不直接读写别家变量；
     2) 夹紧、加工、释放、退回四段动作按状态表推进；
     3) 夹紧超时、加工超时、下游阻塞分别落不同故障码，交整线分级处理；
     4) 急停与恢复由整线广播事件驱动，本块不自己判断安全回路。
   ============================================================ *)

FUNCTION_BLOCK FB_StationCell
VAR_INPUT
    nStationNo     : INT;     (* 工位号，1 起，全线上唯一 *)
    xEnable        : BOOL;    (* TRUE 本工位参与生产 *)
    xPartPresent   : BOOL;    (* 上游在位的物料检测 *)
    xDownstreamOk  : BOOL;    (* 下游可接收 *)
    xClampSensor   : BOOL;    (* 夹紧到位检测 *)
    xRetractSensor : BOOL;    (* 退回原位检测 *)
    xStartPermit   : BOOL;    (* 整线放行 *)
    nCycleLimitMS  : INT;     (* 单件节拍上限毫秒 *)
    xEStop         : BOOL;    (* 急停生效，来自整线 *)
    xFaultReset    : BOOL;    (* 故障复位请求 *)
END_VAR

VAR_OUTPUT
    stStatus     : ST_StationStatus;  (* 对外状态摘要 *)
    xClampCmd    : BOOL;    (* 夹紧输出 *)
    xRetractCmd  : BOOL;    (* 退回输出 *)
    xProcessCmd  : BOOL;    (* 加工启动输出 *)
    xRequestPart : BOOL;    (* 向上游要料 *)
    xReleaseOk   : BOOL;    (* 允许下游取件 *)
    nFaultCode   : WORD;    (* 本工位故障码，0 正常 *)
END_VAR

VAR
    fbFsm       : FB_StateMachine;   (* 工位状态机引擎实例 *)
    aStnNodes   : ARRAY[0..15] OF ST_StateNode;   (* 状态节点表 *)
    aStnTrans   : ARRAY[0..31] OF ST_Transition;  (* 转移规则表 *)
    xTableReady : BOOL;     (* TRUE 表已装载 *)
    nEvent      : INT;      (* 本扫描投给引擎的事件 *)
    wGuard      : WORD;     (* 本扫描守卫位 *)
    wBlock      : WORD;     (* 本扫描封禁位 *)
    nPartId     : INT;      (* 当前工件号，0 空 *)
    nPartSerial : INT;      (* 工件序号自增器 *)
    tonClamp    : TON;      (* 夹紧超时 *)
    tonProcess  : TON;      (* 加工超时 *)
    tonCycle    : TON;      (* 节拍计时 *)
    nElapsedMS  : INT;      (* 节拍已用毫秒 *)
    nFaultLatch : WORD;     (* 故障码锁存，复位才清 *)
    xEStopPre   : BOOL;     (* 上一扫描急停状态，用于边沿检出 *)
    xEStopRise  : BOOL;     (* TRUE 急停刚生效 *)
    xDonePulse  : BOOL;     (* 完成脉冲，仅维持一扫描 *)
    stNodeTmp   : ST_StateNode;    (* 装载节点用临时行 *)
    stTransTmp  : ST_Transition;   (* 装载转移用临时行 *)
    nStateOld   : INT;      (* 上一扫描状态号，用于边沿检出 *)
END_VAR

METHOD PRIVATE LoadTables : BOOL
(* 一次性装载工位状态表；只在首扫描调用，之后只读 *)
VAR
    m : INT;
END_VAR

(* 节点表：0 空闲，10 就绪，20 夹紧，30 加工，40 释放，50 退回，90 故障 *)
FOR m := 0 TO 15 DO
    aStnNodes[m].nState := 0;                (* 先整体清空，避免残留上一次的表 *)
    aStnNodes[m].nParent := -1;
    aStnNodes[m].xLeaf := TRUE;
    aStnNodes[m].nEntryAct := 0;
    aStnNodes[m].nExitAct := 0;
    aStnNodes[m].nTimeoutMS := 0;
    aStnNodes[m].xUsed := FALSE;
    aStnNodes[m].szName := '';
END_FOR;

stNodeTmp.nState := 0;
stNodeTmp.nParent := -1;
stNodeTmp.xLeaf := TRUE;
stNodeTmp.nEntryAct := 0;
stNodeTmp.nExitAct := 0;
stNodeTmp.nTimeoutMS := 0;
stNodeTmp.xUsed := TRUE;
stNodeTmp.szName := 'Idle';
fbFsm.InitNode(0, stNodeTmp);

stNodeTmp.nState := 10;
stNodeTmp.szName := 'Ready';
fbFsm.InitNode(1, stNodeTmp);

stNodeTmp.nState := 20;
stNodeTmp.nTimeoutMS := 1500;      (* 夹紧 1.5 秒不到位即判夹紧故障 *)
stNodeTmp.szName := 'Clamp';
fbFsm.InitNode(2, stNodeTmp);

stNodeTmp.nState := 30;
stNodeTmp.nTimeoutMS := 8000;      (* 加工上限，超时判工艺超时 *)
stNodeTmp.szName := 'Process';
fbFsm.InitNode(3, stNodeTmp);

stNodeTmp.nState := 40;
stNodeTmp.nTimeoutMS := 2000;
stNodeTmp.szName := 'Release';
fbFsm.InitNode(4, stNodeTmp);

stNodeTmp.nState := 50;
stNodeTmp.nTimeoutMS := 2000;
stNodeTmp.szName := 'Retract';
fbFsm.InitNode(5, stNodeTmp);

stNodeTmp.nState := 90;
stNodeTmp.nTimeoutMS := 0;
stNodeTmp.szName := 'Fault';
fbFsm.InitNode(6, stNodeTmp);

(* 转移表：先清空，再逐行写。空槽的 xUsed 必须为 FALSE *)
FOR m := 0 TO 31 DO
    aStnTrans[m].nFrom := 0;
    aStnTrans[m].nEvent := 0;
    aStnTrans[m].wGuard := 0;
    aStnTrans[m].wBlock := 0;
    aStnTrans[m].nTo := 0;
    aStnTrans[m].nAction := 0;
    aStnTrans[m].nTimeMS := 0;
    aStnTrans[m].nPriority := 0;
    aStnTrans[m].xUsed := FALSE;
    aStnTrans[m].szNote := '';
END_FOR;

(* 0 空闲 -> 10 就绪：有料且允许生产 *)
stTransTmp.nFrom := nPhaseIdle;
stTransTmp.nEvent := nEvtStart;
stTransTmp.wGuard := 16#0001;      (* 位0：来料 *)
stTransTmp.wBlock := 0;
stTransTmp.nTo := nPhaseReady;
stTransTmp.nAction := 0;
stTransTmp.nTimeMS := 0;
stTransTmp.nPriority := 10;
stTransTmp.xUsed := TRUE;
stTransTmp.szNote := 'Idle-Ready';
fbFsm.InitTrans(0, stTransTmp);

(* 10 就绪 -> 20 夹紧 *)
stTransTmp.nFrom := nPhaseReady;
stTransTmp.nEvent := nEvtStart;
stTransTmp.wGuard := 16#0001;
stTransTmp.nTo := nPhaseClamp;
stTransTmp.nAction := 21;
stTransTmp.nPriority := 10;
stTransTmp.szNote := 'Ready-Clamp';
fbFsm.InitTrans(1, stTransTmp);

(* 20 夹紧 -> 30 加工：夹紧到位由外部以事件 2 通知 *)
stTransTmp.nFrom := nPhaseClamp;
stTransTmp.nEvent := nEvtDone;
stTransTmp.wGuard := 16#0002;      (* 位1：夹紧到位 *)
stTransTmp.nTo := nPhaseProcess;
stTransTmp.nAction := 31;
stTransTmp.nPriority := 20;
stTransTmp.szNote := 'Clamp-Process';
fbFsm.InitTrans(2, stTransTmp);

(* 20 夹紧超时 -> 90 故障 *)
stTransTmp.nFrom := nPhaseClamp;
stTransTmp.nEvent := nEvtTimeout;
stTransTmp.wGuard := 0;
stTransTmp.nTo := nPhaseFault;
stTransTmp.nAction := 91;
stTransTmp.nPriority := 90;
stTransTmp.szNote := 'ClampTimeout';
fbFsm.InitTrans(3, stTransTmp);

(* 30 加工 -> 40 释放：工艺完成且下游可收 *)
stTransTmp.nFrom := nPhaseProcess;
stTransTmp.nEvent := nEvtDone;
stTransTmp.wGuard := 16#0004;      (* 位2：下游可收 *)
stTransTmp.nTo := nPhaseRelease;
stTransTmp.nAction := 41;
stTransTmp.nPriority := 20;
stTransTmp.szNote := 'Process-Release';
fbFsm.InitTrans(4, stTransTmp);

(* 30 加工超时 -> 90 故障 *)
stTransTmp.nFrom := nPhaseProcess;
stTransTmp.nEvent := nEvtTimeout;
stTransTmp.nTo := nPhaseFault;
stTransTmp.nAction := 92;
stTransTmp.nPriority := 90;
stTransTmp.szNote := 'ProcessTimeout';
fbFsm.InitTrans(5, stTransTmp);

(* 40 释放 -> 50 退回：下游已取走 *)
stTransTmp.nFrom := nPhaseRelease;
stTransTmp.nEvent := nEvtDone;
stTransTmp.wGuard := 16#0008;      (* 位3：下游已取件 *)
stTransTmp.nTo := nPhaseRetract;
stTransTmp.nAction := 51;
stTransTmp.nPriority := 20;
stTransTmp.szNote := 'Release-Retract';
fbFsm.InitTrans(6, stTransTmp);

(* 40 释放超时 -> 90 故障：下游堵了 *)
stTransTmp.nFrom := nPhaseRelease;
stTransTmp.nEvent := nEvtTimeout;
stTransTmp.nTo := nPhaseFault;
stTransTmp.nAction := 93;
stTransTmp.nPriority := 90;
stTransTmp.szNote := 'ReleaseTimeout';
fbFsm.InitTrans(7, stTransTmp);

(* 50 退回 -> 10 就绪：退回原位后等下一件 *)
stTransTmp.nFrom := nPhaseRetract;
stTransTmp.nEvent := nEvtDone;
stTransTmp.wGuard := 16#0010;      (* 位4：退回原位 *)
stTransTmp.nTo := nPhaseReady;
stTransTmp.nAction := 0;
stTransTmp.nPriority := 20;
stTransTmp.szNote := 'Retract-Ready';
fbFsm.InitTrans(8, stTransTmp);

(* 50 退回超时 -> 90 故障 *)
stTransTmp.nFrom := nPhaseRetract;
stTransTmp.nEvent := nEvtTimeout;
stTransTmp.nTo := nPhaseFault;
stTransTmp.nAction := 94;
stTransTmp.nPriority := 90;
stTransTmp.szNote := 'RetractTimeout';
fbFsm.InitTrans(9, stTransTmp);

(* 任意状态 --急停--> 90 故障：全局转移，由引擎按 nFrom = -1 特判 *)
stTransTmp.nFrom := -1;
stTransTmp.nEvent := nEvtEStop;
stTransTmp.wGuard := 0;
stTransTmp.wBlock := 0;
stTransTmp.nTo := nPhaseFault;
stTransTmp.nAction := 95;
stTransTmp.nTimeMS := 0;
stTransTmp.nPriority := 1000;      (* 急停优先级最高，压过一切常规转移 *)
stTransTmp.xUsed := TRUE;
stTransTmp.szNote := 'EStop-Global';
fbFsm.InitTrans(10, stTransTmp);

(* 90 故障 --复位--> 0 空闲 *)
stTransTmp.nFrom := nPhaseFault;
stTransTmp.nEvent := nEvtClear;
stTransTmp.wGuard := 0;
stTransTmp.nTo := nPhaseIdle;
stTransTmp.nAction := 0;
stTransTmp.nPriority := 500;
stTransTmp.szNote := 'Fault-Idle';
fbFsm.InitTrans(11, stTransTmp);

LoadTables := TRUE;
END_METHOD

(* ---------- 主扫描 ---------- *)

IF NOT xTableReady THEN
    LoadTables();                       (* 首扫描装载，只装一次 *)
    xTableReady := TRUE;
END_IF;

(* 急停边沿：整线广播急停事件，全局转移把任何状态拉到故障 *)
xEStopRise := xEStop AND NOT xEStopPre;
xEStopPre := xEStop;

(* 工件号管理：空闲且有料时分配新号，避免同一件被反复计数 *)
IF fbFsm.nStateCur = nPhaseIdle AND xPartPresent AND xEnable AND nPartId = 0 THEN
    nPartSerial := nPartSerial + 1;
    IF nPartSerial > 30000 THEN
        nPartSerial := 1;               (* 编号回绕，避免 INT 溢出 *)
    END_IF;
    nPartId := nPartSerial;
END_IF;

(* 组装本扫描事件：急停 > 故障复位 > 工艺完成 > 启动 *)
IF xEStopRise THEN
    nEvent := nEvtEStop;
ELSIF xFaultReset AND nFaultLatch <> 0 THEN
    nEvent := nEvtClear;
ELSIF fbFsm.nStateCur = nPhaseClamp AND xClampSensor THEN
    nEvent := nEvtDone;
ELSIF fbFsm.nStateCur = nPhaseProcess AND tonProcess.Q THEN
    nEvent := nEvtDone;
ELSIF fbFsm.nStateCur = nPhaseRelease AND NOT xPartPresent AND xDownstreamOk THEN
    nEvent := nEvtDone;
ELSIF fbFsm.nStateCur = nPhaseRetract AND xRetractSensor THEN
    nEvent := nEvtDone;
ELSIF (fbFsm.nStateCur = nPhaseIdle OR fbFsm.nStateCur = nPhaseReady)
      AND xPartPresent AND xStartPermit AND xEnable THEN
    nEvent := nEvtStart;
ELSE
    nEvent := nEvtNone;
END_IF;

(* 守卫位：按位定义，与转移表的 wGuard 一一对应 *)
wGuard := 0;
IF xPartPresent THEN
    wGuard := wGuard OR 16#0001;
END_IF;
IF xClampSensor THEN
    wGuard := wGuard OR 16#0002;
END_IF;
IF xDownstreamOk THEN
    wGuard := wGuard OR 16#0004;
END_IF;
IF NOT xPartPresent AND xDownstreamOk THEN
    wGuard := wGuard OR 16#0008;
END_IF;
IF xRetractSensor THEN
    wGuard := wGuard OR 16#0010;
END_IF;

(* 封禁位：本工位不使能时，除急停外一律不许走 *)
wBlock := 0;
IF NOT xEnable THEN
    wBlock := 16#0001;
END_IF;

fbFsm(xEnable := xEnable OR xEStopRise,
      xReset := FALSE,
      nEventIn := nEvent,
      nInitState := nPhaseIdle,
      wGuardIn := wGuard,
      wBlockIn := wBlock);

(* 动作执行：按引擎给出的状态做输出保持，动作号与表一一对应 *)
xClampCmd := FALSE;
xRetractCmd := FALSE;
xProcessCmd := FALSE;
xReleaseOk := FALSE;
xDonePulse := FALSE;

CASE fbFsm.nStateCur OF
    nPhaseClamp:
        xClampCmd := TRUE;                    (* 夹紧保持输出 *)
    nPhaseProcess:
        xClampCmd := TRUE;
        xProcessCmd := TRUE;                  (* 加工保持输出 *)
    nPhaseRelease:
        xClampCmd := TRUE;
        xReleaseOk := TRUE;                   (* 允许下游取件 *)
    nPhaseRetract:
        xRetractCmd := TRUE;                  (* 退回，夹紧同时释放 *)
    nPhaseReady:
        xRequestPart := TRUE;                 (* 就绪态向上游要料 *)
ELSE
    ;
END_CASE;

(* 进入/离开动作的副作用在这里补齐：引擎只报动作号，落地由本块负责 *)
CASE fbFsm.nLastAction OF
    21:
        tonClamp(IN := TRUE, PT := T#1500MS);   (* 夹紧动作：起超时计时 *)
    31:
        tonProcess(IN := TRUE, PT := INT_TO_TIME(nCycleLimitMS));
    41:
        xDonePulse := TRUE;                     (* 工艺完成脉冲 *)
    51:
        tonProcess(IN := FALSE, PT := T#0MS);   (* 退回：停工艺计时 *)
    91:
        nFaultLatch := 16#0011;                 (* 夹紧超时 *)
    92:
        nFaultLatch := 16#0012;                 (* 工艺超时 *)
    93:
        nFaultLatch := 16#0013;                 (* 下游阻塞超时 *)
    94:
        nFaultLatch := 16#0014;                 (* 退回超时 *)
    95:
        nFaultLatch := 16#0015;                 (* 急停 *)
ELSE
    ;
END_CASE;

(* 离开对应状态就停对应计时，避免残留计时器在下一件上提前超时 *)
IF fbFsm.nStateCur <> nPhaseClamp THEN
    tonClamp(IN := FALSE, PT := T#0MS);
END_IF;
IF fbFsm.nStateCur <> nPhaseProcess THEN
    tonProcess(IN := FALSE, PT := T#0MS);
END_IF;

(* 节拍统计：进入加工开始计，离开释放结束计 *)
IF fbFsm.nStateCur = nPhaseProcess AND nStateOld <> nPhaseProcess THEN
    tonCycle(IN := TRUE, PT := T#60000MS);
END_IF;
IF fbFsm.nStateCur = nPhaseRetract AND nStateOld = nPhaseRelease THEN
    nElapsedMS := TIME_TO_INT(tonCycle.ET);
    tonCycle(IN := FALSE, PT := T#0MS);
END_IF;
nStateOld := fbFsm.nStateCur;

(* 故障状态：锁存并对外报出，工件不自动放行 *)
IF xFaultReset AND NOT xEStop THEN
    nFaultLatch := 0;                    (* 复位只在无急停时接受 *)
END_IF;
nFaultCode := nFaultLatch;

(* 对外摘要 *)
stStatus.nStep := fbFsm.nStateCur;
stStatus.nStateId := fbFsm.nStateLeaf;
stStatus.xBusy := fbFsm.xBusy;
stStatus.xDone := xDonePulse;
stStatus.xReady := (fbFsm.nStateCur = nPhaseReady) OR (fbFsm.nStateCur = nPhaseIdle);
stStatus.xFault := (fbFsm.nStateCur = nPhaseFault) OR (nFaultLatch <> 0);
stStatus.nFaultCode := nFaultCode;
stStatus.nCycleMS := nElapsedMS;
stStatus.xEStopActive := xEStop;

IF fbFsm.nStateCur = nPhaseIdle THEN
    nPartId := 0;                        (* 回到空闲即释放工件号 *)
END_IF;
