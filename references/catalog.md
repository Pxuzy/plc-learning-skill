# 资产目录与规则路由

统一登记 references、模板、示例、scripts、evals 的职责和加载条件，按需读取，不复制规则正文。模板 ID/版本/触发/组合/降级只由 `references/template-index.md` 注册；其它资产随技能版本维护，“当前”参与离线执行，“历史”仅保留兼容。新增资产须登记，缓存不登记。

首列反引号路径只做资产核对，不能建立导航；职责列的主题 Markdown 链接才是按需导航。参考文件仅登记而无可达引用视为孤儿，脚本/evals 登记也不充当语义导航。

## 规则权威与验收证据

每个 ID 指向权威规范与正负证据，模板规定呈现，验证器只检查可确定部分；人工语义验收见 `evals/cases.md`。ID 自 3.17.0 登记，沿用兼容语义。

| 规则 ID | 适用范围与权威来源 | 受影响模板 / 验证器 | 正例 / 负例 | 版本 / 状态 |
|---|---|---|---|---|
| PLC-SAFE-READONLY | 全部讲解；`references/template-index.md` 的只读边界；保护块处理见 workflow | HBK、FB、ST、STATE、INTERFACE、FLOW；`scripts/validate_handbook.py` | `evals/test_handbook_validator.py#test_read_only_safety_boundary_is_allowed` / `evals/test_handbook_validator.py#test_positive_unsafe_recommendations_fail`；保护块另见 Case 18 | 3.17.0 起登记 / 当前 |
| PLC-EVIDENCE-LEVELS | 结构与手册结论；`references/structure-mapping.md` 的四级证据；HBK 仅定义呈现字段 | HBK、MAP；`scripts/validate_structure_map.py` | `evals/test_structure_map.py#test_sample_passes` / `evals/test_structure_map.py#test_relation_table_requires_confidence_column`；真假证据需人工核对 | 3.17.0 起登记 / 当前 |
| PLC-ST-LAYERS | 可读 ST 的层级与阶段；`references/code-reading.md` | ST、HBK；`scripts/validate_handbook.py` 检查块级五部分、关键变量前置与正文实质内容；行内注释门禁另行覆盖执行单元 | `evals/test_handbook.py#test_skill_st_contract_kept` / `evals/test_handbook_validator.py#test_missing_two_pass_fails`；完整分层按 Case 8、21 人工验收 | 3.17.0 起登记 / 当前 |
| PLC-CODE-SOURCE | 源码保真与来源标注；`references/code-reading.md` | HBK、ST、FB；`scripts/check_code_integrity.py`、`scripts/validate_handbook.py` | `evals/test_handbook_validator.py#test_sample_handbook_passes` / `evals/test_handbook_validator.py#test_missing_src_marker_fails`；逐字对账另跑 test_code_integrity | 3.17.0 起登记 / 当前 |
| PLC-COMMENT-VALUE | 完整手册/教学重建及明确要求的教学注释版：执行行须简短业务说明，完整单行单赋值 IF 可共用一句；用户要求整册逐行注释时必须使用 `check_plc_comments.py --require-every-line` 强制每条非空执行/结构行含有效尾注（含闭合行），空白/纯注释行除外；局部 B 默认原码并按前置风格参考追加简洁业务尾注，要求原样源码时不追加；`references/comment-quality.md` | 各源码专题；`scripts/check_plc_comments.py`、`scripts/validate_handbook.py`；最终须逐块语义审查 | `evals/test_comment_quality.py#test_require_every_line_flag_rejects_uncommented_closure_lines` / `evals/test_comment_quality.py#test_handbook_requires_inline_comment_on_each_executable_line`；任意语义正确性须另行核对 | 3.18.1 起登记；3.22.35 严格逐行尾注 / 当前 |
| PLC-SEGMENT-DELIVERY | 长任务自动盘点全部范围、逻辑分段、连续推进、不等逐段确认，跟踪源码覆盖与逐段教学质量双状态，质量未过不得记已讲解，最终合并 Markdown；不得截断源码 | `SKILL.md`、`references/workflow.md` | `evals/test_long_text_delivery.py`、`evals/test_long_text_quality_gate.py`；长文行为见 Case 14 | 3.22.34 更新 / 当前 |
| PLC-KEY-VAR-TYPES | 关键变量表必须含数据类型列；数组写范围与元素类型、结构体写到成员层；允许命名＋注释＋读写辅助推断用途，不按前缀确认类型/作用域；类型影响结论须点明 | `references/handbook-guide.md` | `evals/test_key_var_types.py#test_type_column_required` / `evals/test_key_var_types.py#test_prefix_guessing_forbidden` | 3.22.14 起登记 / 当前 |
| PLC-LAYOUT-PLAIN | 模块编号文首声明且统一；章只放工程内容、模块一律 H3、小节 H4；模块顺序固定；每模块一句“一句话说清”，术语白话、人话先于代码依据 | `references/handbook-guide.md` | `evals/test_layout_plain.py#test_modules_are_h3_not_peer_of_chapters` / `evals/test_layout_plain.py#test_each_module_opens_with_plain_sentence` | 3.22.13 起登记 / 当前 |
| PLC-TITLE-EMOJI | 模块标题表情必填，同类标题固定一组，整篇无表情算版式缺陷；代码与字段内禁放 | `references/handbook-guide.md`、`references/template-handbook.md` | `evals/test_emoji.py#test_rule_requires_title_emoji` / `evals/test_emoji.py#test_rule_no_longer_says_optional` | 3.22.10 起登记 / 当前 |
| PLC-DELIVERY-FORM | 详细讲解与手册最终交付 `.md`；长文可先在聊天自动分段连续完成，再合并成单文件 | `SKILL.md`、`references/handbook-guide.md` | `evals/test_md_delivery.py` / `evals/test_long_text_delivery.py` | 3.22.29 更新 / 当前 |
| PLC-TEMPLATE-COMPOSE | ID、组合、版本与降级；`references/template-index.md` | 全部已注册模板；`scripts/validate_template_index.py`、`scripts/validate_handbook.py` | `evals/test_handbook_validator.py#test_registered_template_composition_is_accepted` / `evals/test_handbook_validator.py#test_unregistered_template_combination_fails` | 3.17.0 起登记 / 当前 |
| PLC-DELIVERY-VERIFY | 复杂框架的依赖驱动学习、覆盖状态、分批合并与完成判定；`references/workflow.md` | HBK、BOOKSET；`scripts/validate_handbook.py`、`scripts/check_code_integrity.py` | `evals/test_handbook_validator.py#test_sample_handbook_passes` / `evals/test_handbook_validator.py#test_final_rejects_unfinished_status`；学习路由见 `evals/test_handbook.py#test_workflow_tracks_progress_by_dependencies_and_evidence` | 3.17.0 起登记；3.22.23 扩展复杂框架引导 / 当前 |
| PLC-SOURCE-DEEP-TEACHING | 真实源码的初学者逐块讲解；[teaching-from-scratch 的源码深讲模式](teaching-from-scratch.md#源码深讲模式读真实工程时加载) | HBK+ST；`evals/test_deep_teaching_contract.py`；格式/围栏检查 | 六槽位、缺口、证据和坏最小 Markdown 拒绝 / 只有代码或变量表而没有因果与扫描变化 | 3.22.0 / 当前 |
| PLC-ORDER-SCOPE | 跨块执行顺序与下标保护范围；`references/teaching-from-scratch.md`（源码深讲的条件式时序）、`references/structure-mapping.md`（证据分级） | HBK+ST；`scripts/validate_handbook.py`；静态检查只覆盖可判定部分 | `evals/test_deep_teaching_contract.py#test_reference_requires_six_source_explanation_slots_and_evidence_gaps` / `evals/test_deep_teaching_contract.py#test_slot_label_alone_is_not_an_explanation`；Task/POU/实参调用顺序仍须人工核对 | 3.22.0 / 当前 |
| PLC-BLOCK-GRANULARITY | 大闭合结构分块：外层骨架 → 内部子块逐段 → 整体汇总；子块边界取闭合结构或语义单元，不切断表达式、单条赋值与原注释；`SKILL.md` 领域底线、`references/local-code-explanation.md` | HBK、ST；`scripts/block_layout.py`、`scripts/validate_handbook.py` | `evals/test_block_layout.py#test_single_closed_structure_over_limit_with_branch_navigation_passes` / `evals/test_block_layout.py#test_many_statements_over_limit_still_rejected` | 当前 |
| PLC-COMMENT-DEFAULT | B 局部与长手册默认追加简洁业务尾注（` // AI: `）；说明对象、动作、结果，空白与纯注释行不补；用户要求原样时不追加；`references/inline-comment-style.md`、`references/local-code-explanation.md` | HBK、ST；`scripts/check_plc_comments.py`、`scripts/validate_handbook.py` | `evals/test_concise_comments.py#test_complete_single_action_if_accepts_one_business_comment` / `evals/test_comment_quality.py#test_handbook_requires_inline_comment_on_each_executable_line` | 当前 |
| PLC-COMMENT-PRECEDENCE | 注释密度与表达以用户当次要求及其指定模板为准，技能默认值不得覆盖；逐行请求不得降级，主要改注释时不重写正文；`references/inline-comment-style.md`、`references/comment-quality.md` | HBK、ST；`scripts/check_plc_comments.py` | `evals/test_comment_quality.py#test_require_every_line_quality_remains_distinct_and_opt_in` / `evals/test_concise_comments.py#test_plain_append_checks_the_new_comment_without_required_prefix` | 当前 |
| PLC-FB-STATE | FB 保持语义分三层：同实例调用间保持属语言语义；首次初值与初始化未见即未知；掉电/下载/RETAIN 未给资料即未知；不得以②③未知否定①；`SKILL.md` 领域底线、`references/code-reading.md` | HBK、ST；`scripts/validate_handbook.py` | `evals/test_first_principles_contract.py#test_short_no_else_example_derives_state_and_two_scans` / `evals/test_handbook_validator.py#test_readable_code_example_requires_initial_state_sequence_and_outcome` | 当前 |
| PLC-TEMPLATE-ADDITIVE | 用户要求在既有模板上增加目录/分章/编号/分块时，原栏目、顺序、变量表、四字段与审查状态逐字保留，新导航放外层或可选槽位；不得改名、合并或重写骨架；`references/template-index.md` | 全部已注册模板；`scripts/validate_template_index.py`、`scripts/validate_handbook.py` | `evals/test_handbook.py#test_template_registry_is_the_single_routing_and_version_source` / `evals/test_handbook_validator.py#test_registered_template_composition_is_accepted` | 当前 |

## References、模板与示例

资产保持 references 原路径。以下均为当前资产；规范随技能，模板版本查索引，示例仅示范结构、非工程事实。状态列简称“规范/注册/模板/示例”。

| 资产 | 职责 | 加载时机 / 场景 | 权威规则 / 验证器 | 版本 / 状态 |
|---|---|---|---|---|
| `references/catalog.md` | [资产职责与规则追踪导航](catalog.md) | 查找资产、规则来源、回归证据 | `scripts/validate_skill.py`；`evals/test_catalog.py` | 规范 |
| `references/template-index.md` | [模板 ID、版本、路由、组合唯一注册表](template-index.md) | 每次选择或组合模板 | `scripts/validate_template_index.py` | 注册 |
| `references/handbook-guide.md` | [手册章节、深度、三层结构、模块五部分、关键变量前置与版式](handbook-guide.md) | 写手册与模块说明 | HBK；`scripts/validate_handbook.py`、`scripts/check_document_layout.py` | 规范 |
| `references/workflow.md` | [生命周期、复杂框架分阶段学习、覆盖状态、分批、完成标准与维护细则](workflow.md) | 复杂框架学习、交付验收、维护技能 | PLC-DELIVERY-VERIFY；`scripts/validate_handbook.py` | 规范 |
| `references/code-reading.md` | [通用第一性原理推导、A/B 短答、ST 分层与源码保真](code-reading.md) | 讲解任何可读代码时，按规模取用 | PLC-ST-LAYERS、PLC-CODE-SOURCE；`evals/test_first_principles_contract.py`、`scripts/check_code_integrity.py` | 规范 |
| `references/one-page-prompt.md` | [一页讲解模板：弱模型复制即用的固定契约（源码保真优先）](one-page-prompt.md) | 模型不遵守长 skill、代码被截短时 | `evals/test_one_page_prompt.py` | 模板 |
| `references/local-code-explanation.md` | [局部五部分块级版式、语义表情、原样源码与因果取证](local-code-explanation.md) | 模式 B：局部代码块默认讲解 | SKILL.md B 路由；`evals/test_entry_routing.py`（静态）；`evals/cases.md` Case 28/29（人工行为验收） | 局部参考 |
| `scripts/local_explanation_contract.py` | 模式 B 字段、表列、执行次数与段末标记的共享契约 | 修改 B 骨架或块级结构门禁后 | `references/local-code-explanation.md`；`evals/test_local_explanation_contract.py` | 脚本 / 当前 |
| `scripts/check_local_explanation.py` | 模式 B 专用出稿检查：元信息、块级结构、原码逐字符对账、源范围映射与待审提示 | B 出稿后按局部参考运行；不替代语义审查 | `references/local-code-explanation.md`；`evals/test_local_explanation_cli.py` | CLI / 当前 |
| `evals/check_local_behavior_artifacts.py` | 本地行为批次冻结清单、请求/候选哈希一致性与格式结果检查 | 仅维护者核对受控本地行为证据时 | `evals/test_local_behavior_artifacts.py`；不调用模型或读取凭据 | CLI / 当前 |
| `evals/fixtures/local-explanation/ton-state.st` | 七行虚构 ST 源码，含定时器、优先分支与末行赋值 | 模式 B 检查器固定输入 | `evals/test_local_explanation_cli.py`、`evals/test_local_teaching_review.py` | 测试夹具 / 非现场工程 |
| `evals/fixtures/complex-st/ST_LineTypes.st` | 虚构整线共用类型声明：状态机节点、转移、工位状态与缓存道结构体 | 复杂 ST 静态检查与层次状态机讲解的固定输入 | `scripts/check_st_logic.py`、`evals/test_st_logic_checker.py` | 合成夹具 / 非现场工程 |
| `evals/fixtures/complex-st/FB_StateMachine.st` | 虚构通用层次状态机引擎：状态集与转移规则全部来自结构体数组，代码不写死步号 | 复杂框架拆解与 ST 静态检查 | `scripts/check_st_logic.py`、`evals/test_st_logic_checker.py` | 合成夹具 / 非现场工程 |
| `evals/fixtures/complex-st/FB_StationCell.st` | 虚构单工位控制块：用状态机引擎驱动夹紧/加工/释放/退回四段，含超时与故障锁存 | 工位层框架讲解与静态检查 | `scripts/check_st_logic.py`、`evals/test_st_logic_checker.py` | 合成夹具 / 非现场工程 |
| `evals/fixtures/complex-st/FB_BufferGate.st` | 虚构缓存道信号量：环形缓存＋预占/确认两阶段，避免上下游互等 | 层间解耦与握手讲解 | `scripts/check_st_logic.py`、`evals/test_st_logic_checker.py` | 合成夹具 / 非现场工程 |
| `evals/fixtures/complex-st/FB_LineScheduler.st` | 虚构整线主调度：工位使能、缓存道仲裁、节拍同步与分级故障 | 整线顶层调度讲解与静态检查 | `scripts/check_st_logic.py`、`evals/test_st_logic_checker.py` | 合成夹具 / 非现场工程 |
| `evals/fixtures/complex-st/FB_AxisHandshake.st` | 虚构轴动作握手层：MC_* 以伪接口声明，指令/执行/完成/故障四态，完成用脉冲 | 运动接口边界讲解与静态检查 | `scripts/check_st_logic.py`、`evals/test_st_logic_checker.py` | 合成夹具 / 非现场工程 |
| `evals/fixtures/local-explanation/ton-state.md` | 与虚构 ST 源对应的填实 B 深讲稿及范围映射 | 离线验证源保真与教学轨迹 | `evals/test_local_explanation_cli.py`、`evals/test_local_teaching_review.py` | 测试夹具 / 非现场工程 |
| `references/quality-checklist.md` | [讲解质量检查清单：事实、必要性、单因素反例、连续轨迹与证据边界；格式和语义分栏](quality-checklist.md) | 生成讲解后自查，或委托 AI 审查质量 | 与 HBK@3.0 块级版式配套；第三部分对应 `evals/test_block_layout.py` 的字段检查 | 检查清单 |
| `references/comment-quality.md` | [注释价值、条件分组、意图与反例](comment-quality.md) | 完整手册/教学重建、明确要求教学注释版，或审查已追加注释；局部 B 依局部模板采用简洁业务尾注，用户要求原样时不追加 | PLC-COMMENT-VALUE；`scripts/validate_handbook.py` | 规范 |
| `references/inline-comment-style.md` | [源码内逐行注释的业务短句风格](inline-comment-style.md) | 每次写注释前加载（含命名辅助推断），恢复时重载；表达口径优先于旧默认删除测试 | PLC-COMMENT-PRECEDENCE | 规范 |
| `references/inline-comment-examples.md` | [11组自造行内注释案例](inline-comment-examples.md) | 与风格规则共同加载，校准条件、赋值、循环、调用、状态与原注释追加 | inline-comment-style | 教学合成；非工程事实 |
| `references/teaching-from-scratch.md` | [教学重建与真实源码深讲的分工、六槽位和协议验收](teaching-from-scratch.md) | 从零带练或初学者需要读懂真实源码 | PLC-SOURCE-DEEP-TEACHING；`evals/test_deep_teaching_contract.py` | 规范 |
| `references/handbook-build-toolchain.md` | [生成器切片、源码保真与校验收敛](handbook-build-toolchain.md) | 生成上千行手册或校验反复返工时 | PLC-CODE-SOURCE；`scripts/check_code_integrity.py` | 规范 |
| `references/source-archive.md` | [只读源码归档、缺口与对账规则](source-archive.md) | 用户只要原样留档、不要讲解时 | PLC-CODE-SOURCE；归档对账 | 规范 |
| `references/locating-and-tracing.md` | [定位、追踪与候选核实：符号查找、声明-写入-消费者链、坐标映射、结论强度](locating-and-tracing.md) | 讲代码前定位对象、追读写与调用关系、核实扫描候选 | PLC-CODE-SOURCE、PLC-EVIDENCE-LEVELS；`scripts/validate_skill.py`、`evals/test_reference_flatness.py` | 规范 |
| `references/structure-mapping.md` | [对象地图、关系证据、四级证据、阅读顺序与漂移](structure-mapping.md) | 写结构分册或判断结构是否过期 | PLC-EVIDENCE-LEVELS；`scripts/validate_structure_map.py` | 规范 |
| `references/common/evidence-and-causality.md` | [证据类别、纸面轨迹与执行因果](common/evidence-and-causality.md) | 判断源码事实、纸面轨迹、推断与未知；写因果与保持结论前 | PLC-EVIDENCE-LEVELS；`evals/check_foundation.py` | 规范 |
| `references/workflows/explain-code.md` | [局部/手册代码讲解流程与长手册分段续接](workflows/explain-code.md) | 按讲解深度执行分析、分段与最终合并 | PLC-SEGMENT-DELIVERY、PLC-BLOCK-GRANULARITY；`evals/check_foundation.py` | 规范 |
| `references/workflows/project-navigation.md` | [复杂工程导航：总览、结构地图与对象选择](workflows/project-navigation.md) | 多对象/复杂框架尚未选定学习范围时 | PLC-EVIDENCE-LEVELS；`templates/project-navigation.md` | 规范 |
| `references/reader-first-progression.md` | [读者递进式讲解：模板被判空泛时的重建骨架](reader-first-progression.md) | 用户否掉模板或要求按第一性原理重做阅读路径时 | PLC-EVIDENCE-LEVELS；`evals/test_handbook.py` | 规范 |
| `references/skill-model-trial.md` | [隔离试跑台、模型/工具调用核对与生成器真实样本验收](skill-model-trial.md) | 换模型或换工具集试跑技能、改造生成器后验收 | 人工验收；`evals/README.md` | 规范 |
| `references/skill-maintenance.md` | [维护入口原文：仓库/安装副本辨认、基线保护、规则承载点与迁移历史](skill-maintenance.md) | 仅维护技能、审计仓库或核对历史模板改造时 | `references/workflow.md`；`evals/test_catalog.py` | 规范 / 维护 |
| `references/external/README.md` | [外部 Skill 案例调研与取舍边界](external/README.md) | 设计工作流时参考，不进入日常讲解 | 非厂商权威；人工 | 调研 / 非运行资产 |
| `references/standards/README.md` | [Skill 格式、平台与厂商资料核对](standards/README.md) | 核对来源层级与能力边界时 | 只读资料；人工 | 调研 / 非运行资产 |
| `references/vendors/README.md` | [厂商资料导航与支持边界](vendors/README.md) | 开展厂商专项说明前 | 只读资料；人工 | 导航 |
| `references/vendors/siemens/README.md` | [西门子资料入口与未验证边界](vendors/siemens/README.md) | 涉及 SCL、I/O、诊断或在线行为前 | 只读资料；人工 | 调研 / 未验证支持 |
| `references/vendors/omron/README.md` | [欧姆龙资料入口与未验证边界](vendors/omron/README.md) | 涉及 ST、I/O、事件或 Cross Reference 前 | 只读资料；人工 | 调研 / 未验证支持 |
| `references/vendors/beckhoff/README.md` | [倍福资料入口与未验证边界](vendors/beckhoff/README.md) | 涉及 TwinCAT ST、GVL、I/O 映射或 EventLogger 前 | 只读资料；人工 | 调研 / 未验证支持 |
| `references/vendors/delta/README.md` | [台达资料入口与未验证边界](vendors/delta/README.md) | 涉及 ISPSoft、ST、I/O 或诊断前 | 只读资料；人工 | 调研 / 未验证支持 |
| `references/omron-smc2-xml-workflow.md` | [SMC2 入库、OEM 工程树、XML/JSON/ST、FB/MFB 读取流程](omron-smc2-xml-workflow.md) | Omron NJ/NX 工程来源 | 只读与源码证据；`scripts/inspect_smc2_archive.py` | 规范 |
| `references/process-and-signal-flow.md` | [工艺/信号规则与 FLOW 双骨架](process-and-signal-flow.md) | 工艺动作、握手、逐跳信号链 | FLOW；`scripts/validate_handbook.py`；规则由本文件维护 | 模板 |
| `references/template-handbook.md` | [HBK 共享字段和手册骨架唯一来源](template-handbook.md) | 默认手册或对象说明基底 | HBK；`scripts/validate_handbook.py` | 模板 |
| `references/template-mfb-xml.md` | [FB 定义、接口、调用实例与内部说明骨架](template-mfb-xml.md) | FB/FC/MFB/POU 讲解 | FB；`scripts/validate_template_index.py`、`scripts/validate_handbook.py` | 模板 |
| `references/template-st-xml-framework.md` | [ST 分层呈现骨架](template-st-xml-framework.md) | 可读 ST 组织与精讲 | ST；`scripts/validate_template_index.py`、`scripts/validate_handbook.py` | 模板 |
| `references/template-state-machine.md` | [STATE 状态转移专题骨架](template-state-machine.md) | 步序、等待、转移与复位 | STATE；`scripts/validate_handbook.py` | 模板 |
| `references/template-interface-instances.md` | [INTERFACE 字典与实例映射骨架](template-interface-instances.md) | 接口、多实例、参数差异 | INTERFACE；`scripts/validate_handbook.py` | 模板 |
| `references/template-overview.md` | [OVR 一屏总览骨架](template-overview.md) | 初次整项目梳理或只要总览 | OVR；`scripts/validate_overview.py` | 模板 |
| `references/template-structure-map.md` | [MAP 结构分册骨架](template-structure-map.md) | 对象清单、执行树、段索引、关系与阅读顺序 | MAP；`scripts/validate_structure_map.py` | 模板 |
| `references/template-handbook-index.md` | [BOOKSET 多册总览与分册索引](template-handbook-index.md) | 多对象拆册 | BOOKSET；`evals/test_handbook.py` | 模板 |
| `references/example-block-handbook.md` | [当前块级手册样例：变量前置、行内注释与整体说明](example-block-handbook.md) | 新稿或检查当前版式 | HBK@3.0；`evals/test_block_layout.py` | 样例 |
| `references/example-handbook.md` | [历史2.x手册兼容与源码标注样例](example-handbook.md) | 仅历史兼容回归，新稿使用example-block-handbook | HBK；`scripts/validate_handbook.py`、`scripts/check_document_layout.py` | 示例 |
| `references/example-fb.md` | [历史2.x假想FB/实例兼容样例](example-fb.md) | 只对照接口证据，不作当前块级版式范本 | HBK、FB、INTERFACE；`scripts/validate_handbook.py` | 示例 |
| `references/example-overview.md` | [一屏总览成品示范](example-overview.md) | OVR 呈现参照 | OVR；`scripts/validate_overview.py` | 示例 |
| `references/example-structure-map.md` | [结构地图成品示范](example-structure-map.md) | MAP 呈现参照 | MAP；`scripts/validate_structure_map.py` | 示例 |

## Scripts

参数以脚本帮助和 workflow 为准；均为当前标准库工具，不改 PLC 工程，默认 CLI 兼容；状态列仅列例外或 CLI。

| 资产 | 职责 | 加载时机 / 场景 | 权威规则 / 验证器 | 版本 / 状态 |
|---|---|---|---|---|
| `scripts/inspect_smc2_archive.py` | 安全清点归档、扩展名与元数据 | SMC2 输入预检 | Omron 工作流；`evals/test_smc2_archive.py` | CLI |
| `scripts/survey_program.py` | 程序统计、地址、调用与跨单元写入候选 | 建立全貌，不代替源码确认 | code-reading；`evals/test_survey_program.py` | CLI |
| `scripts/diff_export.py` | 比较导出单元新增、删除与修改 | 改版后增量讲解 | workflow；`evals/test_diff_export.py` | CLI |
| `scripts/make_manifest.py` | 建源码范围与摘要清单 | 有完整可检索导出，需要逐字对账 | PLC-CODE-SOURCE；`evals/test_make_manifest.py` | CLI |
| `scripts/source_annotations.py` | 共享逐块来源标记语法与邻接绑定 | 修改源码来源契约时 | `references/comment-quality.md`；`evals/test_audit_contracts.py` | 内部共享 |
| `scripts/check_code_integrity.py` | 六项源码完整性与覆盖核对 | 有匹配源文本与 manifest；最终加 --final | PLC-CODE-SOURCE；`evals/test_code_integrity.py` | CLI |
| `scripts/check_markdown_format.py` | 表格、围栏、元信息等格式检查 | 所有成品文档 | handbook-guide；与手册/结构回归配套人工验收 | CLI |
| `scripts/check_document_layout.py` | 标题、顺序、可读性与模块版式 | 成品版式检查 | handbook-guide；`evals/test_document_layout.py` | CLI |
| `scripts/markdown_fences.py` | CommonMark 围栏与正文/源码共享视图 | 修改或诊断 Markdown 围栏行为 | `scripts/check_markdown_format.py`、`scripts/check_document_layout.py`、`scripts/check_plc_comments.py`、`scripts/validate_handbook.py`、`scripts/validate_skill.py`；`evals/test_st_rendering.py` | 共享实现 |
| `scripts/validate_st_rendering.py` | ST 代码围栏配对、标签识别及非法/未闭合行号诊断 | 含 ST 源码或示例的交付文档 | `references/workflow.md`；`evals/test_st_rendering.py` | CLI |
| `scripts/check_content_consistency.py` | 术语、步号、空章、重复段落 | 成品内容一致性检查 | handbook-guide；`evals/test_content_consistency.py` | CLI |
| `scripts/validate_overview.py` | OVR 一屏、六块与索引校验 | 总览交付前 | OVR；`evals/test_overview.py` | CLI |
| `scripts/validate_structure_map.py` | MAP 章节、证据、段索引与阅读顺序 | 结构分册交付前 | MAP、PLC-EVIDENCE-LEVELS；`evals/test_structure_map.py` | CLI |
| `scripts/check_structure_drift.py` | 文档与 manifest 漂移，只报告 | 结构是否过期 | structure-mapping；`evals/test_structure_drift.py` | CLI |
| `scripts/block_layout.py` | 块级五部分、关键变量前置与真实正文检查 | 手册校验器自动调用 | `evals/test_block_layout.py` | 校验器 |
| `evals/test_one_page_prompt.py` | [一页模板契约回归](one-page-prompt.md)：源码保真为第一条硬规则、规则数 ≤6、同一变量字段与五部分骨架、长结构不机械拆断、超限指示不得暗示删除 | 弱模型漏段或截短代码时 | `references/one-page-prompt.md` | 回归 |
| `scripts/validate_handbook.py` | 适用章节、模板组合、模块、安全与来源门禁 | 手册交付前；完整稿加 --final | HBK 与专题；`evals/test_handbook_validator.py` | CLI |
| `scripts/legacy_handbook_validator.py` | 保留旧 `--source/--handbook` 契约：五部分顺序、源码完整覆盖与不回声；仅供旧回归使用，不替代新默认 CLI | 运行 evals/tests/test_handbook_validator.py 或核对历史 CLI 时 | `evals/tests/test_handbook_validator.py` | 兼容 / 维护 |
| `scripts/check_plc_comments.py` | 全文 PLC 围栏逐单元覆盖、可选严格逐行尾注、有限低价值模式及审查记录检查 | 教学注释文档；整册逐行请求加 --require-every-line，最终加 --final 与 --comment-review | PLC-COMMENT-VALUE；`evals/test_comment_quality.py` | 规范；非语义证明 |
| `scripts/validate_template_index.py` | 注册字段、ID、版本、路由与组合对称性 | 改模板或技能后的验证 | template-index；`evals/test_template_index.py` | CLI |
| `scripts/check_st_logic.py` | ST 静态逻辑检查：块/条件配对、CASE 分支覆盖、状态集与转移表一致性、常量越界、死代码与声明卫生；`--min-severity`、`--json`、`--quiet` | 复杂 ST 或层次状态机出稿前；只查可确定结构，不证明语义 | `evals/test_st_logic_checker.py`；夹具见上表 | CLI / 当前 |
| `scripts/git_privacy_gate.py` | 真实暂存树、提交消息、全历史与本地对象库的隐私检查；推送边界失败即阻断 | 提交前、推送前及首次发布前审计 | workflow 版本与 Git 管理；`evals/test_git_privacy_gate.py` | CLI / 无网络 |
| `scripts/validate_skill.py` | 入口结构、catalog 双向资产覆盖与引用可达 | 改技能后；--strict 校验短入口 | catalog；`evals/test_catalog.py`、`evals/test_reference_flatness.py` | 兼容旧入口 |
| `scripts/hooks.py` | 本仓库 hooks 的 install、doctor 与 restore；拒绝未知宿主与覆盖既有委托 | 维护提交门禁或诊断 hook 链时 | `docs/maintenance/governance.md`；`evals/tests/test_hook_chain.py` | CLI / 维护 |
| `scripts/project_policy.py` | 提交格式、暂存树与候选隐私策略的唯一实现；诊断只输出类别与序号 | 修改门禁政策或诊断提交失败时 | `docs/maintenance/governance.md`；`evals/tests/test_governance.py` | CLI / 维护 |

## Evals

`evals/run.py` 自动发现本地 test 文件，不调用模型/联网；历史 JSON 不执行。下列 test 均为当前自动回归，仅查确定性契约，语义/平台另验；其它状态单列。

| 资产 | 职责 | 加载时机 / 场景 | 权威规则 / 验证器 | 版本 / 状态 |
|---|---|---|---|---|
| `evals/README.md` | 离线评估入口与分组说明 | 维护者了解如何运行回归 | `evals/test_offline_runner.py` | 规范 |
| `evals/cases.md` | 人工行为验收场景 | 验证真实讲解质量与证据边界 | 领域 references；人工验收 | 当前 / 非自动执行 |
| `evals/evals.json` | 旧模型行为评测快照 | 仅查历史，不用于当前门禁 | 文件内 legacy 声明；cases 与本地测试为当前依据 | 历史 / 保留兼容 |
| `evals/run.py` | 离线回归 runner | 每轮修改后全量执行 | `evals/test_offline_runner.py` | 当前 / 无网络 |
| `evals/_harness.py` | 进程内脚本调用与输出捕获 | 本地测试复用 | 各脚本 CLI 返回码契约 | 当前 / 测试辅助 |
| `evals/test_catalog.py` | catalog 覆盖、短入口、规则路由、孤儿与断链正反例 | 改入口、目录或资产后 | `scripts/validate_skill.py` | 回归 |
| `evals/test_reference_flatness.py` | 保留旧测试路径，检查入口经 catalog 的两跳可达与锚点 | 引用或路由变化后 | catalog 与 handbook-guide | 回归 |
| `evals/test_md_delivery.py` | 详细讲解与手册最终输出 `.md`；长文允许先聊天自动分段再合并 | 修改交付形态规则后 | `SKILL.md`、`references/handbook-guide.md` | 回归 |
| `evals/test_long_text_delivery.py` | 长文自动清点、逻辑分段、连续全覆盖、状态追踪、最终合并及提前停止负例 | 修改长文分段规则后 | PLC-SEGMENT-DELIVERY；Case 14 | 回归 |
| `evals/test_long_text_quality_gate.py` | 长文逐段语义门槛和交付/讲解双状态；拒绝只贴源码或概述冒充讲解 | 修改长文讲解质量验收后 | PLC-SEGMENT-DELIVERY、Case 14 | 3.22.31 / 当前回归 |
| `evals/test_key_var_types.py` | 关键变量表含类型列、数组/结构体展开；命名推断用途与声明确认类型分开 | 修改变量表契约后 | `references/handbook-guide.md` | 回归 |
| `evals/test_layout_plain.py` | 模块编号统一、模块层级、一句话说清、人话先于代码依据、表情覆盖各级标题 | 修改版式或讲解风格后 | `references/handbook-guide.md`、`SKILL.md` | 回归 |
| `evals/test_title_emoji_gate.py` | 完整手册模块标题缺表情判错、带表情放行、非手册文档不拦 | 修改表情门禁或版式检查后 | `scripts/check_document_layout.py` | 回归 |
| `evals/test_emoji.py` | 标题表情为必填、禁止"表情可选"表述、模板须带表情示例 | 修改版式或表情规则后 | `references/handbook-guide.md`、`references/template-handbook.md` | 回归 |
| `evals/test_unit_language.py` | 混排语言必须逐单元清点再综合结论：清点表、七种情形、禁止整篇单一语言标签 | 修改语言判定或混排规则后 | `references/code-reading.md`、`references/handbook-guide.md` | 回归 |
| `evals/test_holding_semantics.py` | 保持/复位反例不得教错：条件失效只跳过写入，不等于关闭输出；锁定替代直接赋值反例与独立复位路径 | 修改保持/复位教学示例后 | `references/handbook-guide.md`、`references/code-reading.md` | 回归 |
| `evals/test_handbook.py` | 手册默认交付、ST 契约、模板与规则存在性 | 入口或手册契约变化后 | HBK、ST、handbook-guide、workflow | 回归 |
| `evals/test_handbook_validator.py` | 适用性、模块、安全、注释、来源、完成状态正反例 | 手册规则或校验器变化后 | `scripts/validate_handbook.py` | 回归 |
| `evals/test_comment_quality.py` | 注释覆盖/价值、严格逐行尾注与闭合行、词法、库内样例、final 审查正反例 | 注释规则、样例或检查器变化后 | `scripts/check_plc_comments.py`、`scripts/validate_handbook.py` | 回归 |
| `evals/test_concise_comments.py` | 完整单行单赋值 IF 的简洁注释及无前缀追加正反例；保留多动作、低价值与重复检查 | 简洁注释规则或检查器变化后 | `scripts/check_plc_comments.py` | 回归 |
| `evals/test_template_index.py` | 模板注册、组合、路由与版本正反例 | 模板注册变化后 | `scripts/validate_template_index.py` | 回归 |
| `evals/test_code_integrity.py` | 六项源码对账与范围正反例 | 源码引用或完整性规则变化后 | `scripts/check_code_integrity.py` | 回归 |
| `evals/test_make_manifest.py` | 摘要、范围、重复与缺口 | 源清单生成变化后 | `scripts/make_manifest.py` | 回归 |
| `evals/test_diff_export.py` | 新增、删除、改写、行位移差异 | 导出差异逻辑变化后 | `scripts/diff_export.py` | 回归 |
| `evals/test_survey_program.py` | 程序计数、地址、调用与写入 | 统计逻辑变化后 | `scripts/survey_program.py` | 回归 |
| `evals/test_smc2_archive.py` | 归档清点与路径穿越拒绝 | Omron 入库逻辑变化后 | `scripts/inspect_smc2_archive.py` | 回归 |
| `evals/test_overview.py` | 总览合法样例与缺项、超长拒绝 | OVR 骨架或门禁变化后 | `scripts/validate_overview.py` | 回归 |
| `evals/test_structure_map.py` | 结构合法样例、证据列与最终状态 | MAP 骨架或门禁变化后 | `scripts/validate_structure_map.py` | 回归 |
| `evals/test_structure_drift.py` | 摘要不符、单元新增与删除 | 漂移逻辑变化后 | `scripts/check_structure_drift.py` | 回归 |
| `evals/test_document_layout.py` | 合法版式、围栏、层级、表格与顺序 | 版式规则变化后 | `scripts/check_document_layout.py` | 回归 |
| `evals/test_audit_contracts.py` | 源覆盖、长结构、模板成品、局部交付、只读、扫描与围栏贯通正反例 | 审计契约变化后 | 临时源→成品校验链；语义/平台另验 | 回归 |
| `evals/test_entry_routing.py` | A–E、B 五部分/原样源码/表情与公共入口覆盖、最小范围、安全隔离、标题/模式边界变异 | 入口规则或输出规模变化后 | `SKILL.md`、`references/local-code-explanation.md`；其他模式隔离 | 回归 |
| `evals/test_block_layout.py` | 块级样板、变量前置、正文缺失/旧逐句列表反向用例 | 维护当前输出规则 | `scripts/block_layout.py` | 回归 |
| `evals/test_first_principles_contract.py` | 全路由必要性推导、保持/复位、深讲/教学边界、缺推导及源码确认门禁变异 | 讲解路径、模板或示例变化后 | 静态规范契约；不证明会话暂停、模型表现或 ST 编译 | 回归 |
| `evals/test_deep_teaching_contract.py` | 源码深讲六槽位、证据缺口与坏最小 Markdown 拒绝（合成样例，无用户工程源码） | 改源码深讲路由或契约后 | PLC-SOURCE-DEEP-TEACHING；有限模式抽查，非语义证明 | 回归 |
| `evals/test_st_rendering.py` | CommonMark 围栏字符/长度配对、嵌套短示例、ST 标签与行号诊断 | ST 呈现或 Markdown 围栏解析变化后 | `scripts/validate_st_rendering.py` 与共享围栏解析器 | 回归 |
| `evals/test_content_consistency.py` | 术语、步图、空章与重复拒绝 | 一致性规则变化后 | `scripts/check_content_consistency.py` | 回归 |
| `evals/test_git_privacy_gate.py` | 临时真实 Git 仓库验证暂存树/工作区分离、强制暂存、标识及改名源码指纹、消息样式、祖先隐私和推送边界 | 修改 Git 隐私策略与钩子后 | `scripts/git_privacy_gate.py`；无外部远端 | 回归 |
| `evals/test_commit_message_hook.py` | 临时仓库中 repo-local commit-msg 钩子的合法/非法消息集成测试 | 修改仓库自带提交消息门禁后 | `.githooks/commit-msg`、`scripts/git_privacy_gate.py`；临时复制 repo-local hook 与策略 | 回归 |
| `evals/test_offline_runner.py` | runner 本地发现、catalog 测试登记一致性与文档入口契约 | runner 或维护文档变化后 | `evals/run.py`、`scripts/validate_skill.py`、`evals/README.md` | 回归 |
| `evals/test_local_explanation_contract.py` | B 共享字段/表列/执行行数/结束标记和两份骨架的填实门禁 | 修改模式 B 骨架或契约后 | `scripts/local_explanation_contract.py`、`scripts/block_layout.py` | 回归 |
| `evals/test_local_explanation_cli.py` | B CLI 的真实进程返回码、源码逐字符比较、范围映射与缺项拒绝 | 修改 B 出稿检查器或 EOF 契约后 | `scripts/check_local_explanation.py`；固定虚构源夹具 | 回归 |
| `evals/test_local_behavior_artifacts.py` | 本地受控批次请求、冻结候选、清单哈希与格式统计一致性 | 修改行为批次证据检查后 | `evals/check_local_behavior_artifacts.py`；不重放历史请求 | 回归 |
| `evals/test_st_logic_checker.py` | ST 静态检查的退出码、严重级别、JSON 输出、目录递归与编码容错正反例 | 修改 ST 检查器或其夹具后 | `scripts/check_st_logic.py`；只证明结构判定 | 回归 |
| `evals/test_local_teaching_review.py` | TON 假设下固定轨迹的纸面独立重算、反例与零基础覆盖规则 | 修改局部教学样例或审查用例后 | `evals/fixtures/local-explanation/ton-state.md`、`evals/cases.md` Case 29/30 | 回归 / 不证明任意语义 |
| `evals/check_foundation.py` | 基础资产、frontmatter、本地链接与关键契约概念检查 | 迁移或大改技能结构后 | `evals/README.md`；标准库 | CLI / 维护 |
| `evals/tests/host_integration.py` | 真实继承宿主 hooks 的隔离集成检查 | 兼容宿主上人工执行 | `docs/maintenance/governance.md` | 集成 / 可选 |
| `evals/tests/test_governance.py` | 提交政策、候选扫描、隐私负例与 hooks 状态回归 | 修改 project_policy 或 hooks 后 | `scripts/project_policy.py` | 回归 / 维护 |
| `evals/tests/test_handbook_validator.py` | 旧 `--source/--handbook` 契约的结构、顺序、源码覆盖与拒绝输出回归 | 修改兼容校验器后 | `scripts/legacy_handbook_validator.py` | 回归 / 维护 |
| `evals/tests/test_hook_chain.py` | 支持的宿主委托链 stub 回归 | 修改 hooks 委托链后 | `scripts/hooks.py` | 回归 / 维护 |

根目录维护资产：SKILL.md 是入口与技能版本来源，CHANGELOG.md 记录用户可感知变化，LICENSE 保持原授权。它们不在上述三类目录的资产集合内；用户的 WORK_REPORT.md 与 scratch/ 也不参与登记、暂存或自动清理。
