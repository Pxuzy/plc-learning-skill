# PLC 程序学习 Skill

面向初学者，依据可见源码和工程证据解释 PLC 程序。直接提供 ST 或 Ladder 文本即可开始；普通文本讲解不依赖 Python、shell、网络或厂商解析器。运行入口为 [SKILL.md](SKILL.md)，四个品牌目前均为规划目标。

## 当前状态

当前分支正在按[需求对齐实施计划](docs/plans/2026-11-08-plc-skill-requirements-alignment.md)推进。需求追溯、研发调研、核心中文规则、局部模板和一次隔离行为验收已完成首轮；该轮独立复评通过，测试材料与输出保留在仓库外。未提交或合并。单次样稿不代表所有 PLC 方言或品牌均已验证；目标平台加载、PLC 编译、仿真或运行结果也未据此验收。

## 使用与安装

解释文本时阅读入口及对应按需引用即可。Codex 从工作目录向上查找 `.agents/skills/<skill-name>/SKILL.md`；当前仓库根目录的 `SKILL.md` 仍是开发中的主入口，尚未按 Codex 项目路径封装，因此不能声称 Codex 已发现或加载它。真实加载仍需专项测试，见[官方规范核对](references/standards/README.md)。本轮不修改已安装 Skill。

仓库维护门禁需要 Git、Python 3.10+ 和 POSIX shell。仅在获得针对实际仓库的明确授权后才执行安装。安装只修改本仓库局部配置，不修改身份或全局设置：

```sh
python3 -B scripts/hooks.py doctor
python3 -B scripts/hooks.py install
python3 -B scripts/hooks.py doctor
```

`install` 仅支持已核对的宿主委托契约；其他宿主拒绝覆盖。只有在确认没有既有宿主/默认有效 hooks 后，才可显式选择 `install --local-only`。依赖、恢复、隐私边界与提交前置条件见[维护指南](docs/maintenance/governance.md)。这项安装配置的是仓库维护钩子，不是 Skill 平台安装器。

## 维护验证

维护测试的临时文件应写入调用者指定的仓库外 scratch 目录；先设置 `TMPDIR` 指向该目录，不把日志写入版本目录。

```sh
python3 -B -m unittest discover -s evals/tests -v
python3 -B evals/check_foundation.py
python3 -B scripts/project_policy.py candidates
```

在兼容宿主环境可另运行 `python3 -B evals/tests/host_integration.py`，以隔离仓库验证实际 hook 链和提交。[评测说明](evals/README.md)区分实现检查与教学行为验收。

## 资料导航

- [运行与维护边界](docs/architecture/boundaries.md)、[需求追溯](docs/architecture/traceability.md)
- [宿主委托决策](docs/decisions/001-hook-chain.md)、[维护与门禁指南](docs/maintenance/governance.md)
- [模板路由与注册](templates/index.md)、[项目导航模板](templates/project-navigation.md)、[多册手册索引](templates/handbook-index.md)
- [通用证据规则](references/common/evidence-and-causality.md)、[讲解流程](references/workflows/explain-code.md)、[品牌资料状态](references/vendors/README.md)

尚未选择或声明项目许可证。公开分发前需先确认许可；引用官方资料并不自动获得其原文的再分发权。
