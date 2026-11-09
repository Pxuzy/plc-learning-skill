# 简短业务注释：自造示例

以下为独立编写的教学片段，场景和符号均为虚构。只演示行内说明的表达，不是厂商工程导出或可投运程序；未执行 PLC 编译、仿真或硬件验证。

## 示例一：柜内湿度提醒

教学约定：`CabinetHumidityPct` 是已经换算为相对湿度百分数的有效读数；`HumidityWarningPct` 是面板配置的提醒门槛；`PanelHumidityNotice` 只是面板提醒值，不是除湿器输出。三者类型依次为 `REAL`、`REAL`、`BOOL`。语句执行时直接更新提醒，不锁存。

```st
PanelHumidityNotice := CabinetHumidityPct > HumidityWarningPct; // AI: 根据柜内湿度刷新面板提醒
```

这句注释指出处理对象和用途，没有复述“将比较结果赋给布尔变量”。教学取值：读数68.0、门槛64.0时提醒为真；读数61.0时提醒为假。这里的数值只是示例输入，不是设备设定建议；更新面板提醒不证明现场有除湿设备动作。

## 示例二：电表示值换算

教学约定：`MeterPulseCount` 为非负 `DINT` 脉冲累计值，`PulseToKWh` 为 `REAL` 型每脉冲电量，单位为kWh/脉冲；`PanelEnergyKWh` 为 `REAL` 型面板显示值。输入已在演示范围内，不涉及仪表通讯、计费或计数清零。

```st
PanelEnergyKWh := DINT_TO_REAL(MeterPulseCount) * PulseToKWh; // AI: 将累计脉冲换算为面板电量示值
```

这句说明算出的是什么、准备显示什么，不在行尾展开类型转换原理。教学取值：累计250个脉冲，每脉冲0.002kWh，结果为0.5kWh。精度、溢出和采样时机要在真实工程有资料后另行分析。

## 同一语句的取舍

以第二个教学片段为例：

- 合适：“将累计脉冲换算为面板电量示值。”对象、动作和用途明确。
- 需改：“执行一次乘法并写入结果。”只复述运算，没有说明结果是什么。
- 需改：“保存账单并完成扣费。”教学上下文并未提供账单或扣费逻辑。
- 应放正文：“如果计数器溢出，或者其他模块随后覆盖显示值……”这是需要上下文核实的分析，不作为本行默认注释。

## 示例三：按显示模式选择照度示值

教学约定：`LightViewMode` 为 `USINT`，0表示瞬时值、1表示平均值；两个照度输入与显示值均为 `REAL`，单位lx。`PanelLightReady` 为 `BOOL`，只表示选到受支持的模式。

```st
CASE LightViewMode OF // AI: 按面板选项选择照度示值
    0: // AI: 显示当前照度
        PanelLightLux := InstantLightLux; // AI: 将本次照度送到面板
        PanelLightReady := TRUE; // AI: 标记照度示值可用
    1: // AI: 显示平均照度
        PanelLightLux := AverageLightLux; // AI: 将平均照度送到面板
        PanelLightReady := TRUE; // AI: 标记照度示值可用
ELSE // AI: 处理不支持的显示选项
    PanelLightLux := 0.0; // AI: 将照度示值归零
    PanelLightReady := FALSE; // AI: 标记照度示值不可用
END_CASE; // AI: 照度显示选择结束
```

这里相同的可用标记用相同句式，不强行给每行增加不同的分析。若选项为1，瞬时值420.0、平均值390.0，显示390.0且标记为真；选项为9时显示0.0且标记为假。0.0是本例无效模式的占位值，不代表真实照度为零。

## 示例四：有效样本才参与温度换算

教学约定：`ThermoSampleValid` 为 `BOOL`，表示输入采样有效；`ThermoRawWord` 为 `INT`，按摄氏度的十分之一编码。`PanelAirC` 为 `REAL`，`PanelAirReady` 为 `BOOL`。本例只演示显示数据更新。

```st
IF ThermoSampleValid THEN // AI: 采样有效时更新温度显示
    PanelAirC := INT_TO_REAL(ThermoRawWord) / 10.0; // AI: 将温度采样换算为摄氏度
    PanelAirReady := TRUE; // AI: 标记温度示值可用
ELSE // AI: 采样无效时撤销可用标记
    PanelAirReady := FALSE; // AI: 标记温度示值不可用
END_IF; // AI: 温度显示更新结束
```

原始值237时换算为23.7℃；采样无效时不改温度数值，只撤销可用标记。因此旧数值仍可能留在显示变量里，不能把ELSE注释写成“清除温度”。这一点放在段后解释，行尾保持简短。

## 示例五：保存两路光照读数

教学约定：两个实时读数与两个快照变量均为 `REAL`，单位lx；`CaptureLightPair` 为 `BOOL`。这是“条件满足时复制当前值”，没有上升沿检测，也没有定义外部清除请求的方法。

```st
IF CaptureLightPair THEN // AI: 收到采集要求时保存光照读数
    LightSnapshotEast := LightLiveEast; // AI: 保存东侧光照读数
    LightSnapshotWest := LightLiveWest; // AI: 保存西侧光照读数
END_IF; // AI: 两路读数保存结束
```

这段展示连续同类赋值：注释只替换对应对象即可。请求为真、两路读数为312.0和286.0时，两份快照分别更新；请求一直为真时，每次执行都会再次复制，不应注释成“仅保存一次”。请求为假时，本段不改快照。

## 示例六：汇总四路照度

教学约定：`LuxReadings` 为 `ARRAY[1..4] OF REAL`，`LuxTotal`、`LuxMean` 为 `REAL`，`LuxSlot` 为 `INT`。四路值都是有效的lx读数，编号仅为本教学数组位置。

```st
LuxTotal := 0.0; // AI: 清零本轮照度累计值
FOR LuxSlot := 1 TO 4 DO // AI: 依次汇总四路照度
    LuxTotal := LuxTotal + LuxReadings[LuxSlot]; // AI: 将当前通道照度加入累计值
END_FOR; // AI: 四路照度累计结束
LuxMean := LuxTotal / 4.0; // AI: 计算四路照度平均值
```

四路为100.0、120.0、80.0、140.0时，累计440.0、平均110.0。行尾说明正在汇总什么，不展开循环变量的语法教学。每次先清零，避免把上一轮累计值再次算入；缺测或无效通道的处理不在本例中。

## 示例七：按住预览按钮才延时显示提示

教学约定：`PreviewHoldKey` 与 `PanelPreviewHint` 为 `BOOL`；`PreviewDelay` 是一个具有标准非保持通电延时语义的 `TON` 实例，同一实例在每次程序执行时均被调用。`PT` 为 `TIME`，`Q` 为 `BOOL`。本例时间值为虚构演示参数，不指定调用间隔。

```st
PreviewDelay(IN := PreviewHoldKey, PT := T#700ms); // AI: 对预览按钮执行持续按住计时
PanelPreviewHint := PreviewDelay.Q; // AI: 将延时到达结果用于面板提示
```

调用行说明计时用途，下一行说明结果去向；不把调用写成“提示已经亮起”。按本例约定的标准TON语义，按钮保持到门槛且在达到门槛后的调用中，Q为真；未到门槛就松开时，后续以IN为假的调用复位计时结果。这里没有PLC运行证据，实际时间分辨率与平台行为需按目标运行库核对。

## 示例八：记录照明预览按钮的新按下

教学约定：`PreviewTapKey` 为 `BOOL`；`PreviewEdge` 是标准上升沿检测 `R_TRIG` 的同一实例，连续执行且此前已用FALSE输入调用；`PanelPreviewPulse` 为 `BOOL`，仅作软件请求脉冲。

```st
PreviewEdge(CLK := PreviewTapKey); // AI: 检测预览按钮的新按下
PanelPreviewPulse := PreviewEdge.Q; // AI: 生成本次照明预览请求脉冲
```

输入按FALSE、TRUE、TRUE、FALSE依次调用时，按本例语义，输出为FALSE、TRUE、FALSE、FALSE。持续按住不会每次都得到新脉冲。注释点名“请求脉冲”，不宣称灯具已经响应；首次调用前的输入历史已由教学约定限定。

## 示例九：按区间限制亮度设定

教学约定：`BrightnessEntry` 与 `BrightnessAccepted` 为 `INT`；面板输入允许范围为0至100，两端包含。这里的“接受值”只是软件设定，不是灯具实测反馈。

```st
IF BrightnessEntry < 0 THEN // AI: 输入低于下限时采用最低亮度设定
    BrightnessAccepted := 0; // AI: 将接受的亮度设定限制为零
ELSIF BrightnessEntry > 100 THEN // AI: 输入高于上限时采用最高亮度设定
    BrightnessAccepted := 100; // AI: 将接受的亮度设定限制为百分之百
ELSE // AI: 输入在允许区间时保留原设定
    BrightnessAccepted := BrightnessEntry; // AI: 接受面板输入的亮度设定
END_IF; // AI: 亮度设定限制结束
```

输入为-6、45、108时，分别得到0、45、100；输入恰为0或100时走ELSE，数值保持原样。行尾用上下限的业务含义表达判断，不写“进入第一分支”“执行第二赋值”。

## 示例十：用两阶段状态组织曲线预览

教学约定：`ChartPhase` 为 `USINT`，2表示等待、7表示显示；`ChartOpenKey`、`ChartCloseKey`、`PanelChartVisible` 均为 `BOOL`。状态由本段管理，片段执行前已初始化为2。本例只管理面板显示。

```st
CASE ChartPhase OF // AI: 按当前阶段处理曲线预览
    2: // AI: 等待打开曲线预览
        PanelChartVisible := FALSE; // AI: 隐藏面板曲线
        IF ChartOpenKey THEN // AI: 打开要求到来时转入显示阶段
            ChartPhase := 7; // AI: 将曲线预览切换到显示阶段
        END_IF; // AI: 打开要求处理结束
    7: // AI: 显示曲线并等待关闭
        PanelChartVisible := TRUE; // AI: 显示面板曲线
        IF ChartCloseKey THEN // AI: 关闭要求到来时返回等待阶段
            ChartPhase := 2; // AI: 将曲线预览切换到等待阶段
        END_IF; // AI: 关闭要求处理结束
ELSE // AI: 未识别的阶段返回等待状态
    PanelChartVisible := FALSE; // AI: 隐藏面板曲线
    ChartPhase := 2; // AI: 恢复曲线预览的等待阶段
END_CASE; // AI: 曲线预览阶段处理结束
```

阶段2收到打开要求时，本次先隐藏曲线，再把阶段改为7；下一次执行CASE时才进入7分支并显示。关闭同理：7分支本次仍显示，改为2后，下一次执行才隐藏。注释“切换到显示阶段”只说明状态写入，不等于同一行已把可见标记置真。

## 示例十一：已有作者注释时追加教学说明

本节同样是自造材料。教学约定：`PanelNameplateW` 与 `RatedLampW` 均为 `REAL`，单位W；前者为面板额定功率示值，后者为已配置的铭牌额定值，不是实际测量功率。

原行：

```st
PanelNameplateW := RatedLampW; // 面板铭牌栏
```

追加后：

```st
PanelNameplateW := RatedLampW; // 面板铭牌栏 // AI: 将额定功率填入面板铭牌栏
```

原行字符完整保留，新增标记接在作者注释后，仍处于同一条行注释内。再次处理时识别已有 ` // AI: ` 尾注，不再叠加第二份。假设额定值为36.0，面板铭牌栏得到36.0；不能把这行说明成“获取实时耗电功率”。

## 使用时的取舍

这些场景彼此独立，不拼成一套完整控制程序。示例十一展示同一源行的前后对照；其余示例各展示一份代码。行内短句与段后说明分工：前者告诉读者本行的业务作用，后者解释本次写入、未写、顺序或连续执行边界。迁移的是这套表达方法，不是虚构的设备参数或变量含义。
