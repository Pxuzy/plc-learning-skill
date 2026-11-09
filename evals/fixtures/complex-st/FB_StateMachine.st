(* ============================================================
   FB_StateMachine.st —— 通用层次状态机引擎（#9）
   平台：Omron NJ/NX（Sysmac Studio，IEC 61131-3 ST）
   性质：虚构测试夹具，全部名称与逻辑均为合成，无现场地址、无用户工程源码。逻辑自洽、可离线逐行推演，不依赖厂商库。
   设计要点：
     1) 状态集合与转移规则全部来自两个结构体数组，代码不写死步号；
     2) 每扫描至多执行一条转移，避免同周期连跳把动作跳过去；
     3) 层次：子状态转移优先于父状态转移，深度小的优先；
     4) 超时由引擎生成内部事件，业务侧不重复实现；
     5) 非法转换不静默丢弃，落诊断码供上层汇总。
   ============================================================ *)

FUNCTION_BLOCK FB_StateMachine
VAR_INPUT
    xEnable    : BOOL;      (* TRUE 允许引擎执行转移 *)
    xReset     : BOOL;      (* TRUE 清零并回初始态，上升沿生效 *)
    nEventIn   : INT;       (* 上层投递的事件号，0 表示本扫描无事件 *)
    nInitState : INT;       (* 初始状态号，复位后落到此状态 *)
    wGuardIn   : WORD;      (* 上层条件位，转移守卫按位取与 *)
    wBlockIn   : WORD;      (* 上层禁止位，任一位置位即封该转移 *)
END_VAR

VAR_OUTPUT
    nStateCur    : INT;     (* 当前状态号，可能是复合状态 *)
    nStateLeaf   : INT;     (* 当前叶子状态号，动作按它查表 *)
    xBusy        : BOOL;    (* TRUE 处于非空闲状态 *)
    xTimeout     : BOOL;    (* TRUE 本扫描发生停留超时 *)
    nDiagCode    : WORD;    (* 诊断码，0 正常，见文末常量 *)
    nDiagFrom    : INT;     (* 诊断：违规转移的源状态 *)
    nDiagEvent   : INT;     (* 诊断：违规转移的事件号 *)
    nTransCount  : UDINT;   (* 累计成功转移次数，用于观察活性 *)
    nRejectCount : UDINT;   (* 累计被拒绝的转移次数 *)
    nLastAction  : INT;     (* 本扫描执行的转移动作号，0 无 *)
    nLastEntry   : INT;     (* 本扫描执行的进入动作号，0 无 *)
    nLastExit    : INT;     (* 本扫描执行的离开动作号，0 无 *)
END_VAR

VAR
    (* 两张表由上层初始化阶段写入，之后引擎只读 *)
    aNodes       : ARRAY[0..31] OF ST_StateNode;
    aTrans       : ARRAY[0..63] OF ST_Transition;

    xInitDone    : BOOL;    (* TRUE 两张表已初始化 *)
    rTrigReset   : R_TRIG;  (* 复位上升沿 *)
    rTrigTimeout : R_TRIG;  (* 超时事件只投递一次 *)
    tonStay      : TON;     (* 当前状态停留计时 *)
    xStayRun     : BOOL;    (* TRUE 当前状态配了超时且正在计时 *)

    nStatePre    : INT;     (* 上一扫描状态号，用于识别状态切换 *)
    nEventWork   : INT;     (* 本扫描实际处理的事件号 *)
    i            : INT;     (* 表扫描下标 *)
    iBest        : INT;     (* 命中的最优转移行号，-1 未命中 *)
    nBestPri     : INT;     (* 命中的最优优先级 *)
    nBestDepth   : INT;     (* 命中的命中深度，0 为当前态，越大越靠近根 *)
    nDepth       : INT;     (* 单行的命中深度 *)
    xSrcMatch    : BOOL;    (* TRUE 该行源状态命中当前态或某层祖先 *)
    xHit         : BOOL;    (* TRUE 本扫描命中一条转移 *)
    nIdx         : INT;     (* FindNode 输出的行号 *)
    xFound       : BOOL;    (* FindNode 返回值暂存，避免在条件里调用带输出方法 *)

    aAnc         : ARRAY[0..8] OF INT;  (* 当前状态的祖先链，[0] 为父 *)
    nAncCount    : INT;     (* 祖先链长度，0 表示已在顶层 *)
    k            : INT;     (* 祖先链构建下标 *)
    nWalk        : INT;     (* 沿父链行走的暂存 *)
    xWalkDone    : BOOL;    (* TRUE 父链正常回到 -1 *)

    aLeaf        : ARRAY[0..8] OF INT;  (* 下钻路径，用于取第一个叶子 *)
    nLeafCount   : INT;     (* 下钻路径长度 *)
    nCurLeaf     : INT;     (* 下钻过程中当前节点 *)
END_VAR

(* ---------- 表访问：上层初始化时调用 ---------- *)

METHOD PUBLIC InitNode : BOOL
VAR_INPUT
    nIndex : INT;
    stNode : ST_StateNode;
END_VAR
IF nIndex < 0 OR nIndex > 31 THEN
    RETURN;                              (* 越界直接拒绝，不写表 *)
END_IF;
aNodes[nIndex] := stNode;
xInitDone := TRUE;
InitNode := TRUE;
END_METHOD

METHOD PUBLIC InitTrans : BOOL
VAR_INPUT
    nIndex  : INT;
    stTrans : ST_Transition;
END_VAR
IF nIndex < 0 OR nIndex > 63 THEN
    RETURN;
END_IF;
aTrans[nIndex] := stTrans;
xInitDone := TRUE;
InitTrans := TRUE;
END_METHOD

METHOD PRIVATE FindNode : BOOL
(* 按状态号查节点行；找不到时 nIndexOut 为 -1 *)
VAR_INPUT
    nState : INT;
END_VAR
VAR_OUTPUT
    nIndexOut : INT;
END_VAR
VAR
    m : INT;
END_VAR
nIndexOut := -1;
FOR m := 0 TO 31 DO
    IF aNodes[m].xUsed AND aNodes[m].nState = nState THEN
        nIndexOut := m;
        FindNode := TRUE;                (* 只返回第一个匹配行 *)
        RETURN;
    END_IF;
END_FOR;
FindNode := FALSE;
END_METHOD

METHOD PRIVATE BuildAncestors : BOOL
(* 构建当前状态的祖先链；父链超 8 层或缺失即判异常 *)
VAR_INPUT
    nStart : INT;
END_VAR
VAR
    m        : INT;
    nCur     : INT;
    xOk      : BOOL;
    nTmp     : INT;
    xKnown   : BOOL;                     (* 本方法私有查表结果，避免覆盖主扫描的暂存 *)
    nRow     : INT;                      (* 本方法私有行号，同上 *)
    xTopSeen : BOOL;                     (* TRUE 已走到顶层并正常收尾 *)
END_VAR
nAncCount := 0;
nCur := nStart;
xOk := TRUE;
xTopSeen := FALSE;
FOR m := 0 TO 8 DO
    xKnown := FindNode(nCur, nRow);
    IF NOT xKnown THEN
        xOk := FALSE;                    (* 节点表里没有这个状态 *)
        EXIT;
    END_IF;
    nTmp := aNodes[nRow].nParent;
    IF nTmp = -1 THEN
        xTopSeen := TRUE;                (* 到达顶层，链构建完成 *)
        EXIT;
    END_IF;
    IF nTmp = nCur THEN
        xOk := FALSE;                    (* 自指成环 *)
        EXIT;
    END_IF;
    aAnc[nAncCount] := nTmp;
    nAncCount := nAncCount + 1;
    nCur := nTmp;
END_FOR;
IF NOT xTopSeen THEN
    xOk := FALSE;                        (* 8 步内没回到顶层，按成环处理 *)
END_IF;
BuildAncestors := xOk;
END_METHOD

METHOD PRIVATE ResolveLeaf : INT
(* 从当前状态下钻到叶子；复合状态无可用子状态或成环时返回 -1 *)
VAR_INPUT
    nStart : INT;
END_VAR
VAR
    m      : INT;
    q      : INT;
    nCur   : INT;
    nNext  : INT;
    xOk    : BOOL;
    xKnown : BOOL;                       (* 本方法私有查表结果 *)
    nRow   : INT;                        (* 本方法私有行号 *)
END_VAR
nCur := nStart;
FOR m := 0 TO 8 DO
    xKnown := FindNode(nCur, nRow);
    IF NOT xKnown THEN
        ResolveLeaf := -1;
        RETURN;
    END_IF;
    IF aNodes[nRow].xLeaf THEN
        ResolveLeaf := nCur;             (* 已是叶子 *)
        RETURN;
    END_IF;
    nNext := -1;
    FOR q := 0 TO 31 DO
        IF aNodes[q].xUsed AND aNodes[q].nParent = nCur AND aNodes[q].xLeaf THEN
            nNext := aNodes[q].nState;   (* 取第一个子叶子，忽略兄弟顺序之外的信息 *)
            EXIT;
        END_IF;
    END_FOR;
    IF nNext < 0 THEN
        ResolveLeaf := -1;               (* 复合状态无子状态 *)
        RETURN;
    END_IF;
    nCur := nNext;
END_FOR;
ResolveLeaf := -1;                       (* 超过 8 层，判成环 *)
END_METHOD

METHOD PRIVATE RaiseDiag : BOOL
(* 诊断登记：同扫描只保留第一条，避免刷屏 *)
VAR_INPUT
    wCode : WORD;
    nFrom : INT;
    nEvt  : INT;
END_VAR
IF nDiagCode = 0 THEN
    nDiagCode := wCode;
    nDiagFrom := nFrom;
    nDiagEvent := nEvt;
END_IF;
RaiseDiag := TRUE;
END_METHOD

(* ---------- 主扫描 ---------- *)

rTrigReset(CLK := xReset);

IF rTrigReset.Q THEN
    (* 复位优先于一切：清现场，回到初始态，不执行任何动作 *)
    nStateCur := nInitState;
    nStateLeaf := nInitState;
    nStatePre := nInitState;
    nDiagCode := 0;
    nDiagFrom := 0;
    nDiagEvent := 0;
    nTransCount := 0;
    nRejectCount := 0;
    nLastAction := 0;
    nLastEntry := 0;
    nLastExit := 0;
    xTimeout := FALSE;
    xStayRun := FALSE;
    tonStay(IN := FALSE, PT := T#0MS);
    RETURN;
END_IF;

IF NOT xInitDone THEN
    (* 表未就绪：不转移，只对外报当前初始态 *)
    nStateCur := nInitState;
    nStateLeaf := nInitState;
    xBusy := FALSE;
    RETURN;
END_IF;

(* 父链自检：异常时停在原地并落诊断，避免沿坏链乱跳 *)
xWalkDone := BuildAncestors(nStateCur);
IF NOT xWalkDone THEN
    RaiseDiag(16#0001, nStateCur, 0);    (* 父链成环或父状态缺失 *)
    xBusy := FALSE;
    RETURN;
END_IF;

(* 状态切换后重装停留计时，避免把上一状态的时间带入新状态 *)
IF nStateCur <> nStatePre THEN
    nStatePre := nStateCur;
    tonStay(IN := FALSE, PT := T#0MS);
END_IF;

(* 停留计时：PT 取当前节点配置，<=0 视为不设超时 *)
xStayRun := FALSE;
xFound := FindNode(nStateCur, nIdx);
IF xFound THEN
    IF aNodes[nIdx].nTimeoutMS > 0 THEN
        xStayRun := TRUE;
        tonStay(IN := TRUE, PT := INT_TO_TIME(aNodes[nIdx].nTimeoutMS));
    ELSE
        tonStay(IN := FALSE, PT := T#0MS);
    END_IF;
END_IF;

(* 超时事件只在计时到位的那个扫描注入一次，且不覆盖上层已有事件 *)
xTimeout := FALSE;
rTrigTimeout(CLK := tonStay.Q);
IF rTrigTimeout.Q AND xStayRun THEN
    xTimeout := TRUE;
    IF nEventIn = 0 THEN
        nEventWork := nEvtTimeout;
    ELSE
        nEventWork := nEventIn;          (* 上层事件优先，超时顺延到下一扫描 *)
    END_IF;
ELSE
    nEventWork := nEventIn;
END_IF;

(* 选转移：先比优先级，再比命中深度，深度小者（更靠近叶子）优先 *)
iBest := -1;
nBestPri := -32768;
nBestDepth := 99;
xHit := FALSE;
IF xEnable AND nEventWork <> 0 THEN
    FOR i := 0 TO 63 DO
        IF NOT aTrans[i].xUsed THEN
            CONTINUE;                    (* 空槽跳过 *)
        END_IF;
        IF aTrans[i].nEvent <> nEventWork THEN
            CONTINUE;                    (* 事件不匹配，不算违规 *)
        END_IF;
        IF aTrans[i].wBlock = 16#FFFF THEN
            CONTINUE;                    (* 整字封禁，上层用它做整行屏蔽 *)
        END_IF;
        IF (aTrans[i].wBlock AND wBlockIn) <> 0 THEN
            CONTINUE;                    (* 允许位被封：这是合法的“暂不执行” *)
        END_IF;
        IF (aTrans[i].wGuard AND wGuardIn) <> aTrans[i].wGuard THEN
            CONTINUE;                    (* 守卫位不满足 *)
        END_IF;
        (* 源状态匹配：当前态本身、或祖先链上的任一层 *)
        nDepth := 0;
        xSrcMatch := FALSE;
        IF aTrans[i].nFrom = nStateCur THEN
            xSrcMatch := TRUE;
        ELSIF aTrans[i].nFrom = -1 THEN
            (* 全局转移只给急停这类必须无条件生效的事件 *)
            IF nEventWork = nEvtEStop THEN
                xSrcMatch := TRUE;
                nDepth := 9;             (* 深度最大，优先级最低 *)
            END_IF;
        ELSE
            FOR k := 0 TO nAncCount - 1 DO
                IF aTrans[i].nFrom = aAnc[k] THEN
                    xSrcMatch := TRUE;
                    nDepth := k + 1;     (* 越靠根深度越大 *)
                    EXIT;
                END_IF;
            END_FOR;
        END_IF;
        IF NOT xSrcMatch THEN
            CONTINUE;
        END_IF;
        IF aTrans[i].nPriority > nBestPri THEN
            nBestPri := aTrans[i].nPriority;
            nBestDepth := nDepth;
            iBest := i;
            xHit := TRUE;
            CONTINUE;
        END_IF;
        (* 优先级相同时，子状态优先（深度小者胜） *)
        IF aTrans[i].nPriority = nBestPri AND nDepth < nBestDepth THEN
            nBestDepth := nDepth;
            iBest := i;
            xHit := TRUE;
        END_IF;
    END_FOR;
END_IF;

IF NOT xHit THEN
    (* 未命中：本扫描不转移。有事件却无出路时计一次拒绝便于补规则 *)
    IF nEventWork <> 0 AND nEventWork <> nEvtTimeout AND xEnable THEN
        nRejectCount := nRejectCount + 1;
        IF nRejectCount = 1 THEN
            RaiseDiag(16#0002, nStateCur, nEventWork);  (* 事件在当前状态无出路 *)
        END_IF;
    END_IF;
    nStateLeaf := ResolveLeaf(nStateCur);
    xBusy := nStateCur <> nPhaseIdle;
    RETURN;
END_IF;

(* 目标状态必须在节点表内，否则拒绝整条转移并保留原状态 *)
xFound := FindNode(aTrans[iBest].nTo, nIdx);
IF NOT xFound THEN
    RaiseDiag(16#0003, nStateCur, nEventWork);          (* 目标状态未登记 *)
    nRejectCount := nRejectCount + 1;
    nStateLeaf := ResolveLeaf(nStateCur);
    RETURN;
END_IF;

(* 命中后顺序固定：离开动作 -> 切状态 -> 转移动作 -> 进入动作 *)
nLastExit := 0;
xFound := FindNode(nStateCur, nIdx);
IF xFound THEN
    nLastExit := aNodes[nIdx].nExitAct;
END_IF;

nStatePre := nStateCur;
nStateCur := aTrans[iBest].nTo;
nLastAction := aTrans[iBest].nAction;

nLastEntry := 0;
xFound := FindNode(nStateCur, nIdx);
IF xFound THEN
    nLastEntry := aNodes[nIdx].nEntryAct;
END_IF;

(* 切过去之后重新解析叶子；解析不出来说明目标复合状态是空的 *)
nStateLeaf := ResolveLeaf(nStateCur);
IF nStateLeaf < 0 THEN
    RaiseDiag(16#0004, nStateCur, nEventWork);
    nStateLeaf := nStateCur;
END_IF;

nTransCount := nTransCount + 1;
xBusy := nStateCur <> nPhaseIdle;

(* 状态已变化：本次扫描立刻停表，下一扫描按新状态的 PT 重装 *)
tonStay(IN := FALSE, PT := T#0MS);
