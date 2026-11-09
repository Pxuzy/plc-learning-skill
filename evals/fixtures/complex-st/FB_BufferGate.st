(* ============================================================
   FB_BufferGate.st —— 缓存道信号量（#14 整线框架的层间解耦）
   平台：Omron NJ/NX（Sysmac Studio，IEC 61131-3 ST）
   性质：虚构测试夹具，全部名称与逻辑均为合成，无现场地址、无用户工程源码。环形缓存 + 预占/确认两阶段，避免上下游互相等待。
   设计要点：
     1) 入槽、预占、取走三步分离，预占不是取走，确认后才释放；
     2) 预占带超时，上位工位掉链时槽位自动回收，防止整线死锁；
     3) 满/空由引擎维护，业务侧不自己数；
     4) 同一工位重复预占同一槽会被拒绝并落诊断。
   ============================================================ *)

FUNCTION_BLOCK FB_BufferGate
VAR_INPUT
    nSlotCount   : INT;     (* 槽位数，2..32，运行期不变 *)
    xPush        : BOOL;    (* TRUE 请求入槽，上升沿生效 *)
    nPushId      : INT;     (* 入槽工件号 *)
    xPop         : BOOL;    (* TRUE 请求预占，上升沿生效 *)
    nPopOwner    : INT;     (* 预占者工位号 *)
    xConfirm     : BOOL;    (* TRUE 确认取走，上升沿生效 *)
    nConfirmOwner: INT;     (* 确认者工位号，必须与预占者一致 *)
    nReserveMS   : INT;     (* 预占超时毫秒，<=0 不回收 *)
    xFlush       : BOOL;    (* TRUE 清空全部槽位，维护用，上升沿生效 *)
END_VAR

VAR_OUTPUT
    nCount       : INT;     (* 当前槽内工件数，不含已预占 *)
    nReserved    : INT;     (* 已被预占但未确认的槽数 *)
    nFree        : INT;     (* 剩余可入槽数 *)
    xFull        : BOOL;    (* TRUE 无空槽 *)
    xEmpty       : BOOL;    (* TRUE 无工件可预占 *)
    nPopId       : INT;     (* 本次预占到的工件号，0 未取到 *)
    nPopSlot     : INT;     (* 本次预占到的槽号，-1 未取到 *)
    xPopOk       : BOOL;    (* TRUE 本扫描预占成功 *)
    xConfirmOk   : BOOL;    (* TRUE 本扫描确认成功 *)
    nDiagCode    : WORD;    (* 诊断码：0 正常 *)
    nRecycleCnt  : UDINT;   (* 累计因超时回收的预占数 *)
END_VAR

VAR
    aSlots       : ARRAY[0..31] OF ST_BufferSlot;  (* 槽位表 *)
    nHead        : INT;     (* 入槽游标 *)
    nTail        : INT;     (* 出槽游标，按环形顺序推进 *)
    nSlotMax     : INT;     (* 槽位上限，取自 nSlotCount 并做钳位 *)
    rTrigPush    : R_TRIG;  (* 入槽上升沿 *)
    rTrigPop     : R_TRIG;  (* 预占上升沿 *)
    rTrigConfirm : R_TRIG;  (* 确认上升沿 *)
    rTrigFlush   : R_TRIG;  (* 清空上升沿 *)
    aReserveTon  : ARRAY[0..31] OF TON;  (* 每槽预占计时器 *)
    i            : INT;     (* 槽扫描下标 *)
    nScan        : INT;     (* 环形扫描下标 *)
    nCandidate   : INT;     (* 本次候选槽号 *)
    nOwnerPre    : INT;     (* 上一次预占的工位号，用于匹配确认 *)
    nOwnerSlot   : INT;     (* 上一次预占的槽号 *)
    xInitDone    : BOOL;    (* TRUE 槽表已初始化 *)
    nNowMS       : INT;     (* 本扫描时间戳，用累计计时近似 *)
    tonNow       : TON;     (* 全局计时，仅用于取值 *)
END_VAR

METHOD PRIVATE ClampSlotMax : INT
(* 槽位数钳位：低于 2 按 2，高于 32 按 32 *)
IF nSlotCount < 2 THEN
    ClampSlotMax := 2;
ELSIF nSlotCount > 32 THEN
    ClampSlotMax := 32;
ELSE
    ClampSlotMax := nSlotCount;
END_IF;
END_METHOD

METHOD PRIVATE InitSlots : BOOL
VAR
    m : INT;
END_VAR
FOR m := 0 TO 31 DO
    aSlots[m].xUsed := FALSE;
    aSlots[m].nProductId := 0;
    aSlots[m].nEntryMS := 0;
    aSlots[m].xReserved := FALSE;
    aSlots[m].nOwner := 0;
    aReserveTon[m](IN := FALSE, PT := T#0MS);
END_FOR;
nHead := 0;
nTail := 0;
nOwnerPre := 0;
nOwnerSlot := -1;
xInitDone := TRUE;
InitSlots := TRUE;
END_METHOD

METHOD PRIVATE FindPushSlot : INT
(* 从 nHead 起找第一个空槽；环形推进不超过一圈 *)
VAR
    m   : INT;
    nAt : INT;
END_VAR
FOR m := 0 TO nSlotMax - 1 DO
    nAt := (nHead + m) MOD 32;
    IF NOT aSlots[nAt].xUsed THEN
        nHead := nAt;
        FindPushSlot := nAt;
        RETURN;
    END_IF;
END_FOR;
FindPushSlot := -1;                          (* 一圈全满 *)
END_METHOD

METHOD PRIVATE FindPopSlot : INT
(* 从 nTail 起找第一个已入槽、未被预占的工件；保证先进先出 *)
VAR
    m   : INT;
    nAt : INT;
END_VAR
FOR m := 0 TO nSlotMax - 1 DO
    nAt := (nTail + m) MOD 32;
    IF aSlots[nAt].xUsed AND NOT aSlots[nAt].xReserved THEN
        nTail := nAt;
        FindPopSlot := nAt;
        RETURN;
    END_IF;
END_FOR;
FindPopSlot := -1;                           (* 没有可预占的工件 *)
END_METHOD

METHOD PRIVATE Recount : BOOL
(* 重算对外计数，避免增量维护出错 *)
VAR
    m : INT;
END_VAR
nCount := 0;
nReserved := 0;
FOR m := 0 TO 31 DO
    IF aSlots[m].xUsed THEN
        nCount := nCount + 1;
        IF aSlots[m].xReserved THEN
            nReserved := nReserved + 1;
        END_IF;
    END_IF;
END_FOR;
nFree := nSlotMax - nCount;
xFull := nFree <= 0;
xEmpty := nCount = 0;
Recount := TRUE;
END_METHOD

METHOD PRIVATE RecycleExpired : BOOL
(* 回收超时未确认的预占；这是整线防死锁的最后一道闸 *)
VAR
    m : INT;
END_VAR
FOR m := 0 TO 31 DO
    IF aSlots[m].xUsed AND aSlots[m].xReserved THEN
        aReserveTon[m](IN := TRUE, PT := INT_TO_TIME(nReserveMS));
        IF nReserveMS > 0 AND aReserveTon[m].Q THEN
            aSlots[m].xReserved := FALSE;    (* 槽位仍占用，只解除预占 *)
            aSlots[m].nOwner := 0;
            aReserveTon[m](IN := FALSE, PT := T#0MS);
            nRecycleCnt := nRecycleCnt + 1;
            IF nOwnerSlot = m THEN
                nOwnerSlot := -1;            (* 预占句柄同步失效 *)
                nOwnerPre := 0;
            END_IF;
        END_IF;
    ELSE
        aReserveTon[m](IN := FALSE, PT := T#0MS);
    END_IF;
END_FOR;
RecycleExpired := TRUE;
END_METHOD

(* ---------- 主扫描 ---------- *)

IF NOT xInitDone THEN
    nSlotMax := ClampSlotMax();
    InitSlots();
END_IF;

rTrigPush(CLK := xPush);
rTrigPop(CLK := xPop);
rTrigConfirm(CLK := xConfirm);
rTrigFlush(CLK := xFlush);

xPopOk := FALSE;
xConfirmOk := FALSE;
nPopId := 0;
nPopSlot := -1;

(* 清空优先于入出：维护动作用 *)
IF rTrigFlush.Q THEN
    InitSlots();
    nRecycleCnt := 0;
END_IF;

(* 入槽：满则拒绝并落诊断，不排队 *)
IF rTrigPush.Q AND NOT rTrigFlush.Q THEN
    IF nFree <= 0 THEN
        IF nDiagCode = 0 THEN
            nDiagCode := 16#0101;            (* 缓存满，入槽被拒 *)
        END_IF;
    ELSE
        nCandidate := FindPushSlot();
        IF nCandidate < 0 THEN
            IF nDiagCode = 0 THEN
                nDiagCode := 16#0102;        (* 有空位却找不到空槽，表自相矛盾 *)
            END_IF;
        ELSE
            aSlots[nCandidate].xUsed := TRUE;
            aSlots[nCandidate].nProductId := nPushId;
            aSlots[nCandidate].nEntryMS := 0;
            aSlots[nCandidate].xReserved := FALSE;
            aSlots[nCandidate].nOwner := 0;
            aReserveTon[nCandidate](IN := FALSE, PT := T#0MS);
            Recount();
        END_IF;
    END_IF;
END_IF;

(* 预占：取出但不删除，等确认 *)
IF rTrigPop.Q AND NOT rTrigFlush.Q THEN
    IF nOwnerSlot >= 0 THEN
        (* 上一个预占还没确认，不允许再预占，避免槽位被同一工位多占 *)
        IF nDiagCode = 0 THEN
            nDiagCode := 16#0103;            (* 重复预占未确认 *)
        END_IF;
    ELSE
        nCandidate := FindPopSlot();
        IF nCandidate < 0 THEN
            IF nDiagCode = 0 THEN
                nDiagCode := 16#0104;        (* 无工件可预占 *)
            END_IF;
        ELSE
            aSlots[nCandidate].xReserved := TRUE;
            aSlots[nCandidate].nOwner := nPopOwner;
            aReserveTon[nCandidate](IN := TRUE, PT := INT_TO_TIME(nReserveMS));
            nOwnerPre := nPopOwner;
            nOwnerSlot := nCandidate;
            nPopId := aSlots[nCandidate].nProductId;
            nPopSlot := nCandidate;
            xPopOk := TRUE;
            Recount();
        END_IF;
    END_IF;
END_IF;

(* 确认取走：只有预占者本人能确认，且必须指向同一槽 *)
IF rTrigConfirm.Q AND NOT rTrigFlush.Q THEN
    IF nOwnerSlot < 0 THEN
        IF nDiagCode = 0 THEN
            nDiagCode := 16#0105;            (* 无有效预占句柄，确认被拒 *)
        END_IF;
    ELSE
        IF nConfirmOwner <> nOwnerPre THEN
            IF nDiagCode = 0 THEN
                nDiagCode := 16#0106;        (* 确认者与预占者不一致 *)
            END_IF;
        ELSE
            aSlots[nOwnerSlot].xUsed := FALSE;
            aSlots[nOwnerSlot].xReserved := FALSE;
            aSlots[nOwnerSlot].nProductId := 0;
            aSlots[nOwnerSlot].nOwner := 0;
            aReserveTon[nOwnerSlot](IN := FALSE, PT := T#0MS);
            nTail := (nOwnerSlot + 1) MOD 32;  (* 出槽游标前移，保持先进先出 *)
            nOwnerSlot := -1;
            nOwnerPre := 0;
            xConfirmOk := TRUE;
            Recount();
            IF nDiagCode = 16#0104 THEN
                nDiagCode := 0;              (* 之前“无工件”的诊断已不成立，清掉 *)
            END_IF;
        END_IF;
    END_IF;
END_IF;

(* 每扫描都要回收超时预占，不能只在预占沿上做 *)
RecycleExpired();
Recount();

IF nDiagCode <> 0 THEN
    ;                                        (* 诊断由调用方读取后自行清零，这里不自动清 *)
END_IF;
