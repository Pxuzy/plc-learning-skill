# 仓库维护与门禁

## 依赖、诊断与安装

维护工具使用 Git、Python 3.10+ 标准库和 POSIX shell，不会下载或自动安装依赖。普通 PLC 文本讲解不依赖这些工具。已有宿主还需其自身的 privacy scanner 与 `pre-commit` 依赖；本工具检查可识别宿主的本地可执行依赖和政策文件，不要求新机器先安装全局保护。

只有获得当前仓库的明确授权后，才从仓库根目录运行：

```sh
python3 -B scripts/hooks.py install
python3 -B scripts/hooks.py doctor
```

安装仅修改本仓库局部配置，不配置 Git 身份。再次安装只做诊断，不改变配置。POSIX 执行权限必须预先正确；必要时显式运行 `chmod +x .githooks/pre-commit .githooks/commit-msg`。只读 `doctor` 在缺依赖、缺目标、委托无效、宿主内容漂移、配置回环或配置偏离时返回非零，不会自动修复。

若没有有效 `core.hooksPath`、已有委托或有效默认 hooks，可显式选择 `python3 -B scripts/hooks.py install --local-only`。发现宿主配置时该选项会拒绝执行，防止降级既有保护。安装器拒绝未知宿主或覆盖现有委托，也不修改其他项目。链路设计和无法消除的缺失目标跳过行为见[委托决策](../decisions/001-hook-chain.md)。

安装前的局部配置备份，以及工具拥有的配置键、旧值、目标和宿主哈希，保存在 Git common directory 的 `plc-hooks-state.json` 中，不进入版本控制。它属于本机资料。`python3 -B scripts/hooks.py restore` 只恢复工具拥有且仍等于安装值的局部键，然后删除状态文件；它不覆盖整份备份或其他设置。若键已被他人修改则拒绝恢复，应先人工核对状态和当前值，不盲目覆盖。备份丢失时，先只读检查 `git config --show-origin --get core.hooksPath` 与 `git config --show-origin --get privacy.originalHooksPath`，不要猜原值。宿主内容发生漂移时，应重新核对委托契约，不由脚本自动信任新哈希。

## 提交格式

规范源为[需求 §8](../requirements.md#8-git-迭代提交格式与隐私钩子)，机器政策唯一实现位于 `scripts/project_policy.py`。允许的 `type` 为 `feat`、`fix`、`docs`、`refactor`、`chore`、`merge`、`perf`、`release`、`revert`、`test`、`build`、`ci`、`style`。`scope` 只允许 ASCII 英文小写字母（`[a-z]+`）；整行 subject 最多 100 个 Unicode 字符，标题部分至少有一个中文汉字；subject 后必须空一行，后续至少有一条非空 `- ` 正文。不忽略注释行、不自动修复输入；空文件、不可读文件及非 UTF-8 均拒绝。

```text
chore(repo): 准备仓库门禁

- 增加维护工具和合成回归
```

宿主原有格式可能允许更宽的 `scope`；项目政策在其上增加本项目的限制。两个门禁均保留。

## 隐私政策与限制

`pre-commit` 读取暂存变更路径、index 模式和 blob 对象；删除路径也检查名称。`commit-msg` 检查消息格式、消息内容隐私及 Git 当前有效 author/committer identity（包含环境变量覆盖）。这些门禁只检查本次变更，不等于扫描历史。工作树清理不能掩盖暂存问题；未暂存问题另由候选扫描发现。

检查器覆盖常见访问令牌/API key 形状、凭据赋值、私钥头、非公开邮箱、IPv4/IPv6、绝对用户目录、凭据/签名文件、缓存/构建产物及私人材料路径。仅允许 example.com/org/net 邮箱、规范形式的 GitHub `users.noreply` 地址、文档保留网段；凭据占位仅允许大写环境变量引用或固定 `REDACTED`/`PLACEHOLDER`。`.env.example` 只豁免路径名，文件内容仍扫描；docs 或 evals 没有内容豁免。回归中的敏感负例由程序运行时拼接，不把模拟秘密明文写入版本文件。

非 UTF-8、含控制字节、超过 5 MiB、符号链接、submodule 等非普通文件不会自动放行；常见图片、归档和办公文档扩展名也会拒绝。新增二进制资产需另行评估用途与准入。本政策不做通用二进制解码、压缩包分析、熵检测或上下文语义判断；编码/拆分秘密、未知令牌和其他形式的个人材料可能漏检，普通代码也可能误报。它只是有限规则和保守分类，不能提供完整安全保证。

Git 或扫描器异常时失败关闭。项目门禁输出只含风险类别和安全序号，不输出匹配值或候选文件名；不改文件或 index，也没有自定义绕过项。继承宿主的日志行为受宿主自身政策约束，项目工具不能承诺控制其全部输出。

`python3 -B scripts/project_policy.py candidates` 扫描全部未忽略的已跟踪/未跟踪候选文件；显式暂存的忽略材料仍由暂存门禁阻止。`.gitignore` 仅管理常见生成物，不代替准入审查。候选验证还需另行清点被忽略/隐藏的产物；详细目录、哈希、执行日志与报告留在隔离的仓库外位置。

## 验证与首次提交条件

### 当前平台验证矩阵（2026-11-09 迁入后复核）

| 环境/能力 | 结果 | 边界 |
|---|---|---|
| Linux 本机 `evals/tests` 回归 | 36 项全部通过 | 含迁入后的 strict 资产/链接校验、临时仓库真实提交、stub 宿主委托与旧 CLI 兼容校验器；未验证 Windows 与用户实际继承的宿主链 |
| Windows 原生 Python/Git 回归 | 未重跑（上一轮 28 项中 20 项通过） | 上一轮矩阵不适用于迁入后的 36 项；7 项 POSIX hook 测试和 1 项符号链接测试跳过 |
| WSL Ubuntu 22.04 隔离回归 | 未重跑（上一轮 28 项通过） | 上一轮结果保留作历史，不与本轮 Linux 结果合并成“全平台通过” |
| 符号链接 staged-path 回归 | Linux 回归通过；上一轮 Windows 跳过 | Linux 结果不替代 Windows 权限能力验证 |
| 真实项目 hook 安装/doctor/提交 | 安装、doctor 与第一条提交链通过；restore 未执行 | 当前仓库宿主与项目门禁均已实际运行；不代表其他机器链路 |
| 目标平台 Skill 发现/加载 | 未执行 | frontmatter/结构检查不代表已加载 |
| PLC 编译、仿真、Trace、实机 | 未执行 | 不属于本轮静态检查覆盖范围 |

本轮 Linux 命令 `python3 -B -m unittest discover -s evals/tests` 为 36 passed、0 failed；`python3 -B evals/run.py` 为 41 个文件通过；`python3 -B scripts/validate_skill.py . --strict` 与 `python3 -B evals/check_foundation.py` 均为 0 错误。上一轮 Windows 20 passed/8 skipped 与 WSL 28 passed 的结果分开保留，不合并成“全平台通过”。`check_foundation.py` 与 `project_policy.py candidates` 单独执行并分别报告。

将 `TMPDIR` 指向仓库外专用 scratch，运行标准库单元测试、隔离 Git 回归、foundation 检查和候选扫描。在兼容宿主环境另运行真实 host 集成；stub 仅作故障注入，不能代替现场宿主证据。无兼容宿主时明确标未执行。结构脚本不证明教学质量。

首次项目提交还需用户确认公开 author/committer 身份、检查工程树、完成后续自我审查验收，并明确批准提交。维护工具自身不写身份配置、不暂存、不提交、不创建 remote。`doctor` 成功仅表示当时局部 hooks 可达；实际提交链另以提交执行结果为证。本地 hooks 可被 Git 配置或人工改动绕过，不提供服务端强制能力；不自动升版或发布。未获批许可证时不添加虚构许可证。
