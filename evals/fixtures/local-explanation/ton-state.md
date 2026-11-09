# 定时与状态片段 📘

> 工程：虚构教学片段，非现场工程
> 讲解深度：零基础局部深讲
> 讲解版式：块级
> 模块编号：M01 起按源码逻辑顺序

## 整体功能与关键变量 🧭

**控制目标与范围**：可见代码先调用实例，再按故障优先选择是否写状态，最后刷新就绪值。真实工艺目的未知。

| 变量 | 数据类型 | 方向 | 含义 | 谁写谁读 | 证据等级 |
|---|---|---|---|---|---|
| `tonStable` | 未知；下文仅假设标准非保持 TON | 本段调用并读 Q | 在该教学假设下记录输入持续时间 | 调用写实例、分支读 Q；实际库待查 | 未知 |
| `xRequest`、`xPermit` | BOOL；题设声明 | 读 | 调用输入表达式的两个操作数 | 外部写方未知、本段读 | 已确认 |
| `xFault` | BOOL；题设声明 | 读 | 第一分支条件 | 外部写方未知、本段读 | 已确认 |
| `xRun` | BOOL；题设声明 | 写 | 两个分支的赋值目标；跨调用保持仅作假设 | 本段写、消费者未知 | 已确认 |
| `xReady` | BOOL；题设声明 | 写 | 每次写入许可与非故障的合取结果 | 本段写、消费者未知 | 已确认 |

<a id="m01"></a>
### M01 调用与故障优先选择 🧩

**一句话说清**：在标准非保持定时器、同一普通状态存储且无其他写入或初始化的教学假设下，持续输入可以建立状态，故障优先清除；这些不是已核实的工程事实。

#### 1. 功能定位与执行条件 🎯

**功能定位**：每次执行到此处先调用、再选择分支、最后赋值；在上面的教学假设下才把调用解释为持续计时，不承诺真实调用周期。

**代码职责**：调用 tonStable，按 xFault 或 tonStable.Q AND xPermit 选择是否写 xRun，随后写 xReady。

| 进入条件 | 成立时 | 不成立时 | 依据 |
|---|---|---|---|
| 执行到本片段 | 调用实例并执行后续选择和赋值 | 不执行本片段；外部路径未知 | 可见 L1–7，调用者未提供 |
| `xFault` | L3 写 FALSE | 判断 L4；L4 也假则本次不写 xRun | L2–6 |

**设计依据**：若教学目标需要区分持续输入与瞬时输入，就需要时间信息；若要保存接收结果，就需要历史存储。二者不是同一机制，源码不能反证真实工艺需要如此。

#### 2. 源码 💻

**来源定位**：本包虚构教学源 ton-state.st，题设 BOOL 声明不在这七行中，实际库及调用者未知。

<!-- src: none；来源/对象：虚构七行 ST 教学片段 -->
```st
tonStable(IN := xRequest AND xPermit, PT := T#200MS);
IF xFault THEN
    xRun := FALSE;
ELSIF tonStable.Q AND xPermit THEN
    xRun := TRUE;
END_IF;
xReady := xPermit AND NOT xFault;
```

#### 3. 代码块整体讲解 ⚙️

**处理过程**：

<!-- explanation: L1-L1 -->
L1 把两个 BOOL 的 AND（同时为真）送到 IN 输入使能，把 200ms 时长送到 PT 预设时间，再执行实例调用。仅在上述标准 TON 假设下，IN 为假清零、重新为真时从零计时，Q 表示持续时间是否到期；本次调用更新的 Q 供 L4 使用。

<!-- explanation: L2-L3 -->
L2–3 的 IF 是分支选择：xFault 为 TRUE 就执行 L3。`:=` 是把右侧值写入左侧目标，故障路径把 xRun 写成 FALSE。

<!-- explanation: L4-L6 -->
L4–6 的 ELSIF 只有前面的 IF 不成立才判断；Q 和 xPermit 同时为 TRUE 才在 L5 写 TRUE，END_IF 关闭选择结构。两条件均不成立时此选择不写 xRun；在已声明的存储假设下才承接前值。

<!-- explanation: L7-L7 -->
L7 在选择结构之后，每次执行到此处都把 xPermit AND NOT xFault 写入 xReady；NOT 取反。它不读取 xRun，因此不能把 xReady 与 xRun 当成同一状态。

**关键逻辑**：在同一教学假设与初值 xRun=TRUE、IN 已持续 250ms、xFault=TRUE、xPermit=TRUE 下，原版先走故障分支得到 xRun=FALSE。只交换 IF 与 ELSIF 的两个完整分支，其他输入与初值不变，就先命中到期路径得到 TRUE，因此顺序与互斥共同决定优先级。标准 TON 更新后 Q 为真已蕴含本次 IN 为真，所以此假设下只删 L4 的 xPermit，结果局部等价；不能虚构它防止故障后重启。

**写法好处**：两个赋值分支放在一个选择中可直接看出优先级；比较优势仍未知，真实需求和其他写入未给，不能据此保证整机安全。

**状态变化**：xRun 在故障时写 FALSE、非故障且到期/许可同时为真时写 TRUE、其余本次不写；跨调用保持只在上述假设下成立。xReady 每次更新，不以 xRun 为条件。故障不在 TON 的 IN 表达式中，因此不等于定时清零。

#### 4. 形象示例 🧪

**场景设定**：纸面轨迹 A 验证输入中断后不足 200ms 的恢复；轨迹 B 独立从零开始，验证故障期间到期后解除。非实测。

**初始状态**：两轨迹各自假设同实例普通存储、无其他写入/初始化、标准非保持 TON，起点前 ET=0、Q=FALSE、xRun=FALSE、xReady=FALSE；仅列本片段执行时刻，输入在注明区间持续不变。

| 阶段/执行 | 输入与原状态 | 本段处理 | 执行结果 |
|---|---|---|---|
| A 第1次 t=0ms | Request=TRUE, Permit=TRUE, Fault=FALSE；前 ET=0,Q=FALSE,Run=FALSE,Ready=FALSE | 建立计时起点；均不命中 | ET=0,Q=FALSE,Run=FALSE,Ready=TRUE |
| A 第2次 t=250ms | 输入持续不变；前 ET=0,Q=FALSE,Run=FALSE,Ready=TRUE | 已持续250ms，到期分支写 TRUE | ET=200ms,Q=TRUE,Run=TRUE,Ready=TRUE |
| A 第3次 t=260ms | Request=FALSE,Permit=TRUE,Fault=TRUE；前 ET=200ms,Q=TRUE,Run=TRUE,Ready=TRUE | IN 假清零，故障清状态 | ET=0,Q=FALSE,Run=FALSE,Ready=FALSE |
| A 第4次 t=270ms | Request=TRUE,Permit=TRUE,Fault=FALSE；前 ET=0,Q=FALSE,Run=FALSE,Ready=FALSE | 重新建立计时起点 | ET=0,Q=FALSE,Run=FALSE,Ready=TRUE |
| A 第5次 t=370ms | 输入自270ms持续不变；前 ET=0,Q=FALSE,Run=FALSE,Ready=TRUE | 重新累计100ms，未到期；本次不写 Run | ET=100ms,Q=FALSE,Run=FALSE,Ready=TRUE |
| B 第1次 t=0ms | 独立起点 Request=TRUE,Permit=TRUE,Fault=TRUE；前 ET=0,Q=FALSE,Run=FALSE,Ready=FALSE | 建立计时起点，故障写 FALSE | ET=0,Q=FALSE,Run=FALSE,Ready=FALSE |
| B 第2次 t=250ms | 输入持续不变；前 ET=0,Q=FALSE,Run=FALSE,Ready=FALSE | 定时已满，仍由故障优先写 FALSE | ET=200ms,Q=TRUE,Run=FALSE,Ready=FALSE |
| B 第3次 t=260ms | 仅 Fault=FALSE，其余持续；前 ET=200ms,Q=TRUE,Run=FALSE,Ready=FALSE | 不需重新计时，到期分支立即写 TRUE | ET=200ms,Q=TRUE,Run=TRUE,Ready=TRUE |

**理解要点**：A 第5次不能借用 B 的到期值；B 的故障没有中断 IN，因此解除后能在该次置位。均限于此处明确的纸面假设。

#### 5. 程序交互与段间交接 🔗

| 关系 | 来源 | 目标 | 关联变量 | 实际作用 |
|---|---|---|---|---|
| 输入/输出 | 输入写方未知；本段调用和赋值 | 实际消费者未知 | `tonStable.Q`、`xRun`、`xReady` | 调用结果先供本段分支读取；外部消费时机待查 |

**交接要点**：已确认同段先调用后读 Q、随后写 xReady；Task、实例声明、外部写方及消费者均待查，不承诺机械动作。

<!-- 本段已完 -->
