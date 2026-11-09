(* ============================================================
   ST_LineTypes.st —— 整线框架与层次状态机引擎共用的数据类型
   平台：Omron NJ/NX（Sysmac Studio，IEC 61131-3 ST）
   性质：虚构测试夹具，全部名称与逻辑均为合成，无现场地址、无用户工程源码。不含现场地址、真实工艺与厂家库依赖。
   说明：本文件只做声明，不含执行逻辑；类型名统一 ST_ 前缀，
         结构体成员一律带类型前缀，禁止按前缀猜类型。
   ============================================================ *)

TYPE
    (* 层次状态机的状态节点表行 *)
    ST_StateNode : STRUCT
        nState     : INT;      (* 状态号，取值 0..31，全表唯一 *)
        nParent    : INT;      (* 父状态号，-1 表示顶层 *)
        xLeaf      : BOOL;     (* TRUE 叶子状态；FALSE 复合状态，自身不执行动作 *)
        nEntryAct  : INT;      (* 进入动作号，0 无动作 *)
        nExitAct   : INT;      (* 离开动作号，0 无动作 *)
        nTimeoutMS : INT;      (* 停留超时毫秒，<=0 不设超时 *)
        xUsed      : BOOL;     (* TRUE 该行有效，FALSE 空槽 *)
        szName     : STRING[24];
    END_STRUCT;

    (* 层次状态机的转移表行 *)
    ST_Transition : STRUCT
        nFrom     : INT;       (* 源状态号，-1 表示任意状态（全局转移） *)
        nEvent    : INT;       (* 触发事件号 *)
        wGuard    : WORD;      (* 守卫位，需全部置位才允许；0 无条件 *)
        wBlock    : WORD;      (* 阻塞位，任一置位即禁止该转移 *)
        nTo       : INT;       (* 目标状态号 *)
        nAction   : INT;       (* 转移动作号，0 无动作 *)
        nTimeMS   : INT;       (* 转移延迟毫秒，<=0 立即执行 *)
        nPriority : INT;       (* 优先级，数值大者优先 *)
        xUsed     : BOOL;      (* TRUE 该行有效，FALSE 空槽 *)
        szNote    : STRING[32];
    END_STRUCT;
END_TYPE

TYPE
    (* 工位控制块对外暴露的状态摘要，供整线调度读取 *)
    ST_StationStatus : STRUCT
        nStep        : INT;    (* 工位内部步号 *)
        nStateId     : INT;    (* 状态机当前状态号 *)
        xBusy        : BOOL;   (* 工位占用中 *)
        xDone        : BOOL;   (* 本周期加工完成 *)
        xReady       : BOOL;   (* 可接收新工件 *)
        xFault       : BOOL;   (* 故障锁存 *)
        nFaultCode   : WORD;   (* 故障码 *)
        nCycleMS     : INT;    (* 本件节拍毫秒 *)
        xEStopActive : BOOL;   (* 急停生效 *)
    END_STRUCT;

    (* 缓存道的一个槽位 *)
    ST_BufferSlot : STRUCT
        xUsed      : BOOL;     (* TRUE 槽内有工件 *)
        nProductId : INT;      (* 工件号，0 空 *)
        nEntryMS   : INT;      (* 入槽时刻累计毫秒 *)
        xReserved  : BOOL;     (* TRUE 已被某工位预占 *)
        nOwner     : INT;      (* 预占者工位号 *)
    END_STRUCT;
END_TYPE

TYPE
    (* 轴指令伪接口：真实工程里对应 MC_Power / MC_Home / MC_MoveAbsolute 等
       指令实例。此处只保留与握手逻辑相关的字段，不绑定任何实机轴参数。 *)
    ST_AxisCmd : STRUCT
        xExecute   : BOOL;     (* 上升沿触发执行 *)
        xDone      : BOOL;     (* 指令完成反馈 *)
        xFault     : BOOL;     (* 指令故障反馈 *)
        nPosition  : DINT;     (* 目标位置或相对增量 *)
        nVelocity  : DINT;     (* 速度 *)
        nAccel     : DINT;     (* 加速度 *)
    END_STRUCT;
END_TYPE

VAR_GLOBAL CONSTANT
    (* 事件号约定：0 保留为“无事件”，900 以上为引擎内部事件 *)
    nEvtNone      : INT := 0;
    nEvtStart     : INT := 1;
    nEvtDone      : INT := 2;
    nEvtStop      : INT := 3;
    nEvtFault     : INT := 4;
    nEvtClear     : INT := 5;
    nEvtTimeout   : INT := 900;   (* 由引擎在停留超时时自动产生 *)
    nEvtEStop     : INT := 901;   (* 由整线调度广播 *)
    nEvtResume    : INT := 902;   (* 由整线调度广播 *)

    (* 工位/整线的阶段号 *)
    nPhaseIdle      : INT := 0;
    nPhaseReady     : INT := 10;
    nPhaseClamp     : INT := 20;
    nPhaseProcess   : INT := 30;
    nPhaseRelease   : INT := 40;
    nPhaseRetract   : INT := 50;
    nPhaseDone      : INT := 60;
    nPhaseFault     : INT := 90;

    (* 整线故障分级：0 无故障，1 可自恢复，2 需人工，3 安全停 *)
    nSevNone      : INT := 0;
    nSevRecover   : INT := 1;
    nSevManual    : INT := 2;
    nSevSafeStop  : INT := 3;
END_VAR
