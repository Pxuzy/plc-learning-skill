# 需求到责任与证据

本表索引需求，不复制运行规则。需求全文见[快照](../requirements.md)，阶段定义见[完整计划](../plans/development-plan.md)。实现级测试只证明被测行为，用户树检查和后续自我审查验收均未完成。

| 需求 | 责任目录 / 规则 | 当前证据与待办 |
|---|---|---|
| §1 目标 | SKILL.md、references/common/ | 基础规则已有；D–G 证明实际教学和扩展 |
| §2 分级与教学 | references/workflows/ | P0/P1/P2/P3 已有，D/E 行为待验 |
| §3 识别、品牌、工程树 | references/vendors/、docs/architecture/ | 原索引及本轮职责边界；F 需授权样本 |
| §3.6 借鉴 | docs/architecture/boundaries.md | 继承渐进读取、证据分级与职责分离；不复制旧版式、专用实现或历史 |
| §4 因果与批判审查 | references/common/、workflows/ | 规则与案例卡已有；D 新鲜语义输出未跑 |
| §5 嵌套覆盖 | references/workflows/ | E 长文连续生成、合并与保真待验 |
| §6 AI 注释 | SKILL.md、references/workflows/ | 教学副本规则已有；D/E 保真和例外待验 |
| §7 格式与隐私 | references/standards/、scripts/project_policy.py | 官方文档有限核对、内容正反例；真实发现加载未验 |
| §8 格式门禁 | scripts/project_policy.py、.githooks/ | 单一规则实现；所有类型和长度边界回归 |
| §8 安全接入 | scripts/hooks.py、docs/decisions/ | 本地委托、doctor、配置恢复及隔离 Git 提交验证；无法消除 Git 绕过能力 |
| §9 可读性 | references/workflows/ | 已有规则；D/E 用户产物试读待验 |
| §10 验收 | evals/ | foundation 与治理实现测试；不等于教学或最终验收 |
| §11 流程 | docs/plans/、maintenance/ | 仅 A/B/C 准备；保留未提交文件，树检查后才后续验收 |
| §12 已确认 | docs/requirements.md | 规范保留；发布才升版，本轮不提交、不发布 |
| §13 待确认 | docs/plans/ | 平台策略、样本、教学门槛、团队与发布分别归 A/D/E/F/G；待定仍待定 |

首次提交身份与项目提交许可独立于脚本通过；没有用户确认的公开身份，不配置或推定身份可发布。详细执行日志和文件哈希在独立执行正文报告中，版本文档不保存机器路径、原始诊断和配置快照。
