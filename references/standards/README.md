# 官方格式与平台资料核对

查阅日期：2026-11-08。此页区分通用 Skill 文件格式、运行平台发现/加载和 PLC 厂商资料。某一层通过不代表其他层兼容。

## Skill 格式与运行平台

| 来源 | 本次核对的窄结论 | 采用方式与限制 |
|---|---|---|
| [Agent Skills Specification](https://agentskills.io/specification) | Skill 以独立目录中的 `SKILL.md` 为入口；`name` 与目录名一致，`description` 说明用途及适用时机，并可将详细资料分离后按需引用。 | 作为文件结构和渐进披露基线；符合文件规范不构成任何宿主平台发现、加载或行为兼容证明。 |
| [Anthropic Agent Skills: Best Practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices) | 官方编写建议强调明确描述何时使用、渐进披露和按需分离参考资料。 | 采用短入口、按任务路由和单一权威参考；其宿主发现目录与 Codex 不可互相推定。 |
| [Codex: Build skills](https://developers.openai.com/codex/skills/) | Codex 支持显式和按描述隐式调用 Skill；仓库级发现位置是 `.agents/skills/`，并从当前目录向上扫描至仓库根目录。Skill 可把长资料放在 references 等目录按需读取。 | 本仓库根目录的 `SKILL.md` 不位于发现目录；未做隔离安装/发现测试，不声称当前 Codex 已加载。 |
| [Codex: Custom instructions with AGENTS.md](https://developers.openai.com/codex/agent-configuration/agents-md) | `AGENTS.md` 用于全局/项目持续指引，并按目录层级组合；它与通过 `.agents/skills/` 发现的按需 Skill 属于不同入口和职责。 | 本仓库提供的 `AGENTS.md` 不会将根目录 `SKILL.md` 自动变成 Skill；真实发现、加载和交互仍需隔离实测。 |

## 厂商资料入口

| 厂商/资料 | 可支持的结论范围 | 限制 |
|---|---|---|
| [Siemens Diagnostics Overview for S7-1200/S7-1500](https://support.industry.siemens.com/cs/attachments/109752283/109752283_Diagnostic_Overview_DOC_V10_en.pdf) | 官方 V1.0 文档（2018-09）按系统/设备诊断、程序错误和过程诊断等场景整理诊断入口，包括 TIA Portal 在线功能、Trace、错误 OB、诊断指令及 HMI 报警。 | 仅是 S7-1200/S7-1500 诊断概览，文中以 S7-1500 CPU/Comfort Panel 举例；不能外推到所有 Siemens 产品/版本，也不验证本仓库的方言或工程解析。 |
| [Omron Sysmac Studio 产品规格](https://www.ia.omron.com/products/family/3077/specification.html) | 面向 NJ/NX/NY 控制器的 Sysmac Studio Ver.1 规格页（页面标注更新于 2026-10-01）说明 Cross Reference 可列出变量、数据类型、I/O 端口、函数和功能块的使用位置。 | 这是软件规格，不是某个工程的交叉引用结果；使用时仍需核对控制器、软件版本及目标对象。 |
| [Beckhoff TwinCAT PLC Intro: GVL](https://infosys.beckhoff.com/content/1033/tc3_plc_intro/2530218891.html)、[I/O 配置概览](https://infosys.beckhoff.com/content/1033/tc3_io_intro/1094759563.html)、[EventLogger](https://infosys.beckhoff.com/content/1033/tceventlogger/12332564491.html) | 官方页说明 GVL 用于声明/编辑/显示全局变量；I/O 配置包含设备、过程映像和映射；TcEventLogger 消息使用 Source ID/Event ID 并由客户端呈现。 | 页面是术语和证据入口，不代表目标工程有这些配置；EventLogger 组件、TwinCAT/运行时版本须与实际项目匹配。 |
| [Delta ISPSoft 产品页](https://www.deltaww.com/en-US/products/PLC-Programmable-Logic-Controllers/3598?categoryCode=060301) | Delta 官方产品页将 ISPSoft 标为 Programming Software 并链接 Download Center。 | 下载中心旧地址会转到动态新路由，本次无法读取目录正文；尚未锁定 PLC 系列、ISPSoft 版本或对应 ST 手册章节，不据此声称格式解析或 ST 行为已验证。 |

厂商专属问题须先确认品牌、产品线、软件/固件版本和工程对象，再引用匹配资料的具体章节。资料只用于支持其明确陈述的窄事实；项目结构、调用关系、I/O 连线、事件记录和运行结果仍须工程或运行时证据。

## 当前验证状态

- 已核对：Agent Skills 目录/元数据/渐进披露规范、Codex `.agents/skills/` 仓库发现路径及 `AGENTS.md` 项目指引的不同职责；Siemens S7-1200/S7-1500 V1.0 诊断概览、Omron Ver.1 Cross Reference 规格、Beckhoff GVL/I/O/EventLogger 资料，以及 Delta ISPSoft 产品页。
- 未核验：目标平台中的实际 Skill 发现/加载、安装包布局、规则行为、PLC 编译/仿真/Trace/实机结果，以及具体工程解析。
- 不变约束：Skill 自有说明和默认交付使用简体中文；平台固定元数据键、源码、厂商对象名、命令、URL 保留原样。
