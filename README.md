# PLC 程序学习 Skill

面向初学者，以可见源码和工程证据讲解 PLC 程序。直接提供 ST 或 Ladder 文本即可使用；普通讲解不依赖 Python、shell、网络或厂商解析器。运行入口是 [SKILL.md](SKILL.md)，四品牌目前均为规划目标。

当前仅完成第一阶段 A/B/C 的准备实现；先由用户检查实际工程树，再开展后续自我审查验收。尚无项目提交，不代表教学效果、平台加载、PLC 编译或运行通过。完整路线见[开发计划](docs/plans/development-plan.md)，规范目标见[需求快照](docs/requirements.md)。

## 使用与安装

阅读入口及其按需引用即可解释文本。平台安装时应将运行资料放入名为 `plc-program-learning` 的 Skill 目录；当前开发仓库根目录名与元数据名不同，不能把本仓库根目录自动发现视为已验证。目标平台发现与加载仍待专项测试，参见[官方规范核对](references/standards/README.md)。本轮不修改已安装 Skill。

仓库维护门禁需要 Git、Python 3.10+ 和 POSIX shell。先只读诊断，安装时仅写本仓库局部配置，不修改身份或全局设置：

```sh
python3 -B scripts/hooks.py doctor
python3 -B scripts/hooks.py install
python3 -B scripts/hooks.py doctor
```

`install` 针对已核对的宿主委托契约；其他宿主拒绝覆盖。无宿主的新环境才可显式使用 `install --local-only`。依赖、恢复、隐私边界与首次提交前置条件统一见[维护指南](docs/maintenance/governance.md)。此安装仅安装维护钩子，不是 Skill 平台安装器。

## 维护验证

维护测试临时文件需在调用者指定的仓库外 scratch 目录生成，先设置 `TMPDIR` 指向该目录；不要使用版本目录存日志。

```sh
python3 -B -m unittest discover -s evals/tests -v
python3 -B evals/check_foundation.py
python3 -B scripts/project_policy.py candidates
```

有兼容宿主时另运行 `python3 -B evals/tests/host_integration.py`，以隔离仓库验证实际链和真实提交。[评测说明](evals/README.md)区分上述实现检查与待开展的教学验收。

## 资料导航

- [运行与维护边界](docs/architecture/boundaries.md)、[需求追溯](docs/architecture/traceability.md)
- [宿主委托选择](docs/decisions/001-hook-chain.md)、[唯一门禁操作说明](docs/maintenance/governance.md)
- [通用证据规则](references/common/evidence-and-causality.md)、[讲解流程](references/workflows/explain-code.md)、[品牌状态](references/vendors/README.md)

尚未选择或声明项目许可证；公开分发前需确认许可，不因引用官方资料而获得其原文再分发权。
