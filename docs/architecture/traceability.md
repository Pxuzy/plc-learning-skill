# 需求、责任与验证追溯

需求基准为仓库内[需求规格](../requirements.md)，实施顺序见[当前分支计划](../plans/2026-11-08-plc-skill-requirements-alignment.md)。本表记录规则归属和实际验证状态，不将目录存在或文档措辞当作功能通过。

| 优先级与需求 | 权威实现位置 | 机械/行为验证 | 状态与边界 |
|---|---|---|---|
| P0 源码范围、保真与事实/推断/未知边界 | `SKILL.md`、`references/common/evidence-and-causality.md`、`references/workflows/explain-code.md`、`templates/code-explanation.md` | 模板/结构回归；完整范围与逐项语义审查 | 隔离样稿复评已通过；该结论不证明真实品牌工程的全量覆盖；样本与衍生事实不入库 |
| P0 条件、顺序、读写、未写与状态因果 | `references/common/evidence-and-causality.md` | 合成轨迹；人工 PLC 语义审查 | 当前规则有基础，行为正确性未由结构检查证明 |
| P0 有信息增量的 `AI:` 注释和逐条删除测试 | `SKILL.md`、`references/workflows/explain-code.md`、`templates/code-explanation.md` | 结构检查只能验证规则存在；人工判断信息价值、源码映射和删除影响 | 默认逐行为现行口径；选择性注释仅 `--legacy-selective` 复核历史夹具；隔离样稿复评已通过，不代表跨品牌工程支持 |
| P0 需求范围覆盖、初学者可读和批判审查 | `SKILL.md`、解释工作流、局部讲解模板 | 完整源码呈现、合成/获准输入上的输出审阅 | 规则与模板已落地；隔离样稿复评已通过；未发现缺陷不等于程序完美 |
| P0 完整讲解以 `.md` 文件交付并提供位置 | `SKILL.md`、`references/workflows/explain-code.md`、`references/workflows/project-navigation.md`、`templates/index.md`、`templates/handbook-index.md`、`scripts/validate_handbook.py` | 文件交付契约回归；合成手册源码覆盖回归；检查用户路径优先、不覆盖既有文件，隔离评测产物不入仓库 | 交付规则和结构/源码覆盖验证器已通过合成回归；尚未运行真实 PLC 讲解文件交付 |
| P0 验证诚实与隐私隔离 | `evals/README.md`、维护规范 | 文件候选扫描、输出审阅、隔离边界核验 | 私有最终测试输入及衍生材料不入仓库；样本语义结论仅在隔离评测时确认 |
| P1 整体调用、状态及跨对象关系 | `references/workflows/`、对应 `references/vendors/` | 获准工程证据上的逐跳核验 | 只在用户要求或任务跨对象时触发；纯文本片段不声称全工程覆盖 |
| P1 复杂工程学习导航与用户选择 | `SKILL.md`、`references/workflows/project-navigation.md`、`templates/index.md`、`templates/project-navigation.md`、`templates/handbook-index.md` | 导航与模板结构回归通过；真实工程上的对象盘点与用户选择验收 | 已验证流程入口、可选对象、等待选择、多册索引与 Markdown 交付规则存在；真实品牌工程结构识别和端到端选择行为仍未验证 |
| P1 品牌、I/O、事件或诊断专项 | `references/vendors/`、`references/standards/` | 精确到品牌/产品线/格式/版本的官方资料与获准工程实证 | 资料索引不等于解析或运行时支持；缺匹配证据时标未知 |
| P1 深度轨迹、边界反例及长文连续合并 | `references/workflows/explain-code.md`、局部/手册模板 | 可复算轨迹、段落/源码映射及合并检查 | 按请求和代码复杂度触发；短答不强套完整结构 |
| P2 第一性原理、系统视角、额外示例/图表 | 讲解正文；必要时引用相关参考 | 人工相关性与证据复核 | 仅在帮助当前问题时加入，不得挤占 P0 |
| P3 Skill 研发调研、仓库门禁、版本与发布治理 | `docs/`、`scripts/`、`.githooks/`、`evals/` | 隔离 Git 回归、资料追溯、独立审查 | 仅维护任务执行，不进入普通代码讲解 |
| P3 平台发现与真实加载 | `references/standards/README.md`、发布资料 | 官方说明 + 目标平台真实发现/加载测试 | 格式层面有资料；当前尚未在 Codex 或其他目标平台完成真实加载验证 |
| P3 品牌工程解析与能力声明 | `references/vendors/`，以后按需添加解析器/回归 | 每个具体组合的获准样本和真实解析/运行证据 | 四品牌仍为规划范围；`.st` 文本本身不足以验证工程树、调用、变量表或 I/O 映射 |

## 职责边界

- 用户需求定义目标、范围、隐私约束和验收方向；本计划把需求拆成实现批次及阶段门。
- `SKILL.md` 路由日常请求；`references/` 定义按需加载的解释规则与有来源边界的厂商资料；`templates/` 只定义确有重复需求的交付形状。
- `scripts/` 与 `evals/` 负责可重复的维护检查和合成回归；脚本不判定教学价值、PLC 语义或现场安全。
- 开发者负责需求追溯、优秀案例/官方资料筛选、实现及如实报告；PLC 专业/独立审阅负责核对语义证据；用户审阅产物并决定是否进入后续验收或发布。
- 提交、推送、合并、安装和发布分别受单独授权约束。当前分支可审阅，不表示已获提交或合并许可。

## 本阶段完成条件

每条需求均有权威位置、验证方式、状态及未决边界；P0 不因 P2/P3 维护项而降级。只有真实运行证据才能提升兼容或解析等级。样本评测源、输出、日志、哈希和可识别摘要均留在仓库外隔离目录，文档只记录不指向具体私有样本的通用状态。
