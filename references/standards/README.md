# Standards Notes / 官方规范有限核对

2026-11-06 查阅 [Agent Skills Specification](https://agentskills.io/specification) 与 [OpenAI Codex Skills](https://developers.openai.com/codex/skills/)（后者当日重定向到 [Build skills](https://learn.chatgpt.com/docs/build-skills)）。仅将公开网页用于元数据和资料组织核对；抓取证据留在独立执行记录，不复制官方原文进入本仓库，也不据此取得再分发许可。

| 项目 | 官方约定与当前结论 |
|---|---|
| 入口 | Skill 目录至少有 `SKILL.md`；当前入口存在 |
| 必需元数据 | `name` 与 `description`；当前两者非空，无个人身份字段 |
| name | 1–64 字符，小写字母/数字/连字符，不能首尾连字符或连续连字符，须与父目录名一致；当前 `plc-program-learning` 合法，但开发目录名不同，安装包必须采用同名目录 |
| description | 1–1024 字符，说明能力和何时触发；当前值在此界限内 |
| 可选字段 | license、compatibility、metadata 等按规范选择；不为匿名化补造身份或许可证，当前省略 |
| 内容组织 | 相对引用及渐进加载；普通文本讲解不依赖维护 Python，较长规则位于 references |
| Codex 发现 | 官方描述仓库/用户等作用域的 `.agents/skills` 发现位置和按名称/描述选用、再读取正文；根目录出现 SKILL.md 不足以证明已被发现 |
| AGENTS.md | 可用于工程指引/引用，不把这种文本引用等同于 Codex 标准 Skill 安装或真实发现 |

`evals/check_foundation.py` 只做基础结构/链接/措辞检查，不是完整 YAML/spec 验证器。此处文档核对不宣称 Anthropic/Codex 兼容认证；入口目录名问题在本阶段保留，后续分发时解决，真实发现/加载与无 Python 行为仍待专项验证。品牌/PLC 平台规范须另按实际型号和版本验证。
