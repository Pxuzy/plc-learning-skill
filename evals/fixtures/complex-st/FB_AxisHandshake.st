(* ============================================================
   FB_AxisHandshake.st —— 轴动作握手层（#14 的运动接口边界）
   平台：Omron NJ/NX（Sysmac Studio，IEC 61131-3 ST）
   性质：虚构测试夹具，全部名称与逻辑均为合成，无现场地址、无用户工程源码。MC_* 指令在本文件里以“伪接口”声明，
         只保留可离线推演的握手语义，不绑定任何实机轴参数。
   设计要点：
     1) 一条轴同一时刻只允许一个动作在飞，重复下指令直接拒绝；
     2) 指令、执行中、完成、故障四态，完成用脉冲上报，不保持；
     3) 超时与软限位在本地判，不依赖伺服自己报；
     4) 回零、点动、绝对定位走同一状态机，避免三套逻辑各写一遍。
   ============================================================ *)

FUNCTION_BLOCK FB_AxisHandshake
VAR_INPUT
    xEnable      : BOOL;     (* TRUE 本轴允许动作 *)
    nCmd         : INT;      (* 指令号：0 无，1 回零，2 绝对，3 相对，4 点动，5 停 *)
    nTarget      : DINT;     (* 目标位置，单位由上层约定 *)
    nVelocity    : DINT;     (* 速度 *)
    nAccel       : DINT;     (* 加速度 *)
    nTimeoutMS   : INT;      (* 单次动作超时毫秒，<=0 用默认 *)
    nPosLimit    : DINT;     (* 软正限位 *)
    nNegLimit    : DINT;     (* 软负限位 *)
    xServoOn     : BOOL;     (* 伺服使能反馈 *)
    xHomeSensor  : BOOL;     (* 原点开关 *)
    nActualPos   : DINT;     (* 实际位置反馈 *)
    xEStop       : BOOL;     (* 急停 *)
    xReset       : BOOL;     (* 故障复位 *)
END_VAR

VAR_OUTPUT
    xBusy        : BOOL;     (* TRUE 动作执行中 *)
    xDone        : BOOL;     (* TRUE 本扫描动作完成，脉冲 *)
    xFault       : BOOL;     (* TRUE 动作层故障 *)
    nFaultCode   : WORD;     (* 故障码，0 正常 *)
    nState       : INT;      (* 握手状态号 *)
    nPosOut      : DINT;     (* 本扫描下发的目标位置 *)
    xServoCmd    : BOOL;     (* 伺服使能指令 *)
END_VAR

VAR
    (* 伪接口：真实工程里这些是 MC_Power / MC_Home / MC_MoveAbsolute
       等指令实例；此处只保留字段形状，便于离线推演与逻辑审查 *)
    stPower      : ST_AxisCmd;   (* 使能指令 *)
    stHome       : ST_AxisCmd;   (* 回零指令 *)
    stMoveAbs    : ST_AxisCmd;   (* 绝对定位指令 *)
    stMoveRel    : ST_AxisCmd;   (* 相对定位指令 *)
    stMoveJog    : ST_AxisCmd;   (* 点动指令 *)

    nStIdle      : INT := 0;     (* 空闲 *)
    nStWaitServo : INT := 10;    (* 等伺服就绪 *)
    nStMoving    : INT := 20;    (* 动作中 *)
    nStDone      : INT := 30;    (* 完成，冲一拍 *)
    nStFault     : INT := 90;    (* 故障 *)

    nStateCur    : INT;          (* 当前握手状态 *)
    nCmdLatch    : INT;          (* 已接受但未执行完的指令号 *)
    nTargetLatch : DINT;         (* 已锁定的目标位置 *)
    nTimeoutUse  : INT;          (* 实际生效的超时值 *)
    tonMove      : TON;          (* 动作超时 *)
    rTrigCmd     : R_TRIG;       (* 指令上升沿，避免同一指令重复触发 *)
    rTrigReset   : R_TRIG;       (* 复位上升沿 *)
    nCmdPre      : INT;          (* 上一扫描指令号 *)
    xLimitHit    : BOOL;         (* TRUE 目标越过软限位 *)
    nDelta       : DINT;         (* 相对定位用的增量 *)
    xHomeOk      : BOOL;         (* TRUE 回零完成 *)
    nErrLatch    : WORD;         (* 故障码锁存 *)
END_VAR

METHOD PRIVATE CheckCommand : BOOL
(* 指令合法性：先判使能，再判限位，最后判是否有动作在飞 *)
VAR_INPUT
    nCmdIn : INT;
END_VAR
CheckCommand := FALSE;

IF NOT xServoOn THEN
    nErrLatch := 16#0301;                    (* 伺服未就绪，任何动作都不发 *)
    RETURN;
END_IF;

IF nStateCur = nStMoving THEN
    nErrLatch := 16#0302;                    (* 已有动作在飞，拒绝新指令 *)
    RETURN;
END_IF;

CASE nCmdIn OF
    1:
        CheckCommand := TRUE;                (* 回零不受软限位约束 *)
    2:
        IF nTarget > nPosLimit THEN
            nErrLatch := 16#0303;            (* 目标越过正软限位 *)
            RETURN;
        ELSIF nTarget < nNegLimit THEN
            nErrLatch := 16#0304;            (* 目标越过负软限位 *)
            RETURN;
        END_IF;
        CheckCommand := TRUE;
    3:
        nDelta := nTarget;
        IF nActualPos + nDelta > nPosLimit THEN
            nErrLatch := 16#0305;            (* 相对位移会撞正限位 *)
            RETURN;
        ELSIF nActualPos + nDelta < nNegLimit THEN
            nErrLatch := 16#0306;
            RETURN;
        END_IF;
        CheckCommand := TRUE;
    4:
        CheckCommand := TRUE;                (* 点动由上层限时，不在这里判 *)
    5:
        CheckCommand := TRUE;                (* 停止永远允许 *)
ELSE
    nErrLatch := 16#0307;                    (* 未登记指令号 *)
END_CASE;
END_METHOD

METHOD PRIVATE StartMotion : BOOL
(* 按指令号分派到对应伪指令；真实工程里这里是调用 MC_* 实例 *)
VAR_INPUT
    nCmdIn : INT;
END_VAR
nTargetLatch := nTarget;
nPosOut := nTarget;

CASE nCmdIn OF
    1:
        stHome.xExecute := TRUE;             (* 回零：清执行位以外的字段 *)
        stHome.nPosition := 0;
    2:
        stMoveAbs.xExecute := TRUE;
        stMoveAbs.nPosition := nTargetLatch;
        stMoveAbs.nVelocity := nVelocity;
    3:
        stMoveRel.xExecute := TRUE;
        stMoveRel.nPosition := nDelta;
        stMoveRel.nVelocity := nVelocity;
    4:
        stMoveJog.xExecute := TRUE;
        stMoveJog.nVelocity := nVelocity;
    5:
        ;                                    (* 停止不需要目标，直接断执行位 *)
ELSE
    ;
END_CASE;

nCmdLatch := nCmdIn;
tonMove(IN := TRUE, PT := INT_TO_TIME(nTimeoutUse));
nStateCur := nStMoving;
StartMotion := TRUE;
END_METHOD

METHOD PRIVATE StopMotion : BOOL
(* 断全部执行位：停止、故障、急停都走这里，保证只在一处收口 *)
stHome.xExecute := FALSE;
stMoveAbs.xExecute := FALSE;
stMoveRel.xExecute := FALSE;
stMoveJog.xExecute := FALSE;
tonMove(IN := FALSE, PT := T#0MS);
StopMotion := TRUE;
END_METHOD

(* ---------- 主扫描 ---------- *)

rTrigReset(CLK := xReset);

IF rTrigReset.Q AND NOT xEStop THEN
    (* 复位：清故障与握手，不清位置与限位 *)
    nErrLatch := 0;
    nCmdLatch := 0;
    nStateCur := nStIdle;
    StopMotion();
    xFault := FALSE;
    nFaultCode := 0;
END_IF;

(* 急停：最高优先，任何状态都断执行位并进故障 *)
IF xEStop THEN
    nErrLatch := 16#0308;
    StopMotion();
    nStateCur := nStFault;
END_IF;

(* 伺服使能指令：与使能输入同相，不额外加延时 *)
xServoCmd := xEnable AND NOT xEStop;
stPower.xExecute := xServoCmd;

nTimeoutUse := nTimeoutMS;
IF nTimeoutUse <= 0 THEN
    nTimeoutUse := 5000;                     (* 默认 5 秒，避免调用方漏配就无限等 *)
END_IF;

(* 指令沿检出：同一指令号连续多扫描只算一次 *)
rTrigCmd(CLK := nCmd <> 0 AND nCmd <> nCmdPre);
nCmdPre := nCmd;

xDone := FALSE;

CASE nStateCur OF
    nStIdle:
        xBusy := FALSE;
        IF NOT xServoOn AND xEnable THEN
            nStateCur := nStWaitServo;       (* 想动但伺服没起来，先去等 *)
        ELSIF rTrigCmd.Q AND xEnable THEN
            IF CheckCommand(nCmd) THEN
                StartMotion(nCmd);
            ELSE
                nStateCur := nStFault;
            END_IF;
        END_IF;

    nStWaitServo:
        xBusy := FALSE;
        IF xServoOn THEN
            nStateCur := nStIdle;            (* 伺服起来了，回空闲等指令 *)
        ELSIF NOT xEnable THEN
            nStateCur := nStIdle;            (* 上层撤回使能，不必再等 *)
        END_IF;

    nStMoving:
        xBusy := TRUE;
        (* 完成判定按指令类型分开：回零看原点，其余看位置到位 *)
        CASE nCmdLatch OF
            1:
                xHomeOk := xHomeSensor AND stHome.xDone;
                IF xHomeOk THEN
                    nStateCur := nStDone;
                END_IF;
            2, 3:
                IF stMoveAbs.xDone OR stMoveRel.xDone THEN
                    nStateCur := nStDone;
                END_IF;
            4:
                IF NOT xEnable THEN
                    nStateCur := nStDone;    (* 点动只在使能期间有效 *)
                END_IF;
            5:
                nStateCur := nStDone;        (* 停止立即算完成 *)
        ELSE
            ;
        END_CASE;
        (* 超时与外部故障在任何指令下都要判 *)
        IF tonMove.Q THEN
            nErrLatch := 16#0309;
            StopMotion();
            nStateCur := nStFault;
        ELSIF stMoveAbs.xFault OR stMoveRel.xFault OR stHome.xFault THEN
            nErrLatch := 16#030A;
            StopMotion();
            nStateCur := nStFault;
        END_IF;

    nStDone:
        xBusy := FALSE;
        xDone := TRUE;                       (* 完成只冲一拍，不保持 *)
        StopMotion();
        nCmdLatch := 0;
        nStateCur := nStIdle;

    nStFault:
        xBusy := FALSE;
        StopMotion();
        (* 故障态不自动回空闲，必须等复位，避免故障件被继续加工 *)
        ;

ELSE
    nStateCur := nStFault;
    nErrLatch := 16#030B;
END_CASE;

nState := nStateCur;
xFault := nStateCur = nStFault;
nFaultCode := nErrLatch;
