# 仓库维护与门禁操作

## 依赖与安装

维护工具使用 Git（实际链测试需要 `git hook run`）、Python 3.10+ 标准库和 POSIX shell；不下载或自动安装依赖。普通 PLC 文本解释没有这些依赖。已有宿主还需要它自己的 privacy scanner 与 pre-commit 依赖；本工具检查已识别宿主的本地可执行依赖及政策文件，不要求新机器先安装全局保护。

从仓库根目录运行 `python3 -B scripts/hooks.py install`，随后运行 `python3 -B scripts/hooks.py doctor`。安装仅修改当前仓库局部配置，不配置身份；再次安装只诊断，配置不变。执行权限必须预先正确，必要时显式修复 `chmod +x .githooks/pre-commit .githooks/commit-msg`。只读 doctor 在缺依赖、缺目标、失效委托、宿主内容漂移、回环或配置偏离时非零，不自动修复。

没有有效 `core.hooksPath`、已有委托或有效默认 hooks 的新仓库，可选择 `python3 -B scripts/hooks.py install --local-only`。有宿主配置时此参数拒绝，禁止用它降级现有宿主链。安装器拒绝未知宿主、不覆盖已有委托，也不修改其他项目。链设计与无法防止的缺失目标跳过见[决策](../decisions/001-hook-chain.md)。

安装前完整局部配置备份及所拥有的键、旧值、目标和宿主哈希存于 Git common directory 中的 `plc-hooks-state.json`，不进版本控制。它是本机资料。`python3 -B scripts/hooks.py restore` 仅恢复安装器拥有且仍等于安装值的局部键，删除状态；不覆盖整份备份或无关设置。键已被别人改动时拒绝，先人工核对状态和当前设置，不盲目覆盖。若备份丢失，先只读检查 `git config --show-origin --get core.hooksPath` 与 `git config --show-origin --get privacy.originalHooksPath`，不要猜测原值。宿主内容漂移需重新核对契约，不在此脚本内自动信任新哈希。

## 提交格式

规范源为[需求 §8](../requirements.md#8-git-迭代提交格式与隐私钩子)，机器政策唯一实现位于 `scripts/project_policy.py`。允许类型：`feat`、`fix`、`docs`、`refactor`、`chore`、`merge`、`perf`、`release`、`revert`、`test`、`build`、`ci`、`style`。scope 仅 ASCII 英文小写字母（`[a-z]+`）；整行 subject 最多 100 个 Unicode 字符，标题部分至少含一个中文汉字；subject 后必须空一行，后续至少一条有内容的 `- ` 正文。不跳过注释行或自动修复输入，空文件、不可读文件和非 UTF-8 均拒绝。

```text
chore(repo): 准备仓库门禁

- 增加维护工具和合成回归
```

宿主原有格式允许更宽的 scope，项目政策额外收紧到本项目要求；两个门禁都保留。

## 隐私政策与限制

pre-commit 读取暂存变更名称、index 模式与 blob 对象，删除路径也检查名称。只检查本次变更内容，不等于扫描历史。工作树清理不能掩盖暂存问题；未暂存问题由候选扫描另行发现。commit-msg 分别检查消息格式和隐私；两个阶段均检查 Git 当前有效 author/committer identity（包含环境覆盖），不替用户选择身份。

检查包括常见访问令牌/API key 形状、凭据赋值、私钥头、非公开邮箱、IPv4/IPv6、绝对用户目录、凭据/签名文件、缓存/构建产物及私人材料路径。只允许 example.com/org/net 邮箱、规范形态的 GitHub users.noreply 地址、文档保留网段；凭据占位仅大写环境变量引用或固定 `REDACTED`/`PLACEHOLDER`。`.env.example` 仅名称例外，内容仍扫描；不豁免 docs 或 evals。回归的敏感负例由代码运行时拼接，不把完整模拟秘密写进版本文件。

非 UTF-8、含控制字节、超过 5 MiB、符号链接、submodule 等非普通文件拒绝自动放行；常见图片、归档、办公文档等材料扩展名也拒绝。需要新增二进制资产时另做用途和准入方案。本政策没有通用二进制解码、压缩包分析、熵检测或上下文语义判断；其他格式的个人材料、编码/拆分秘密和未知令牌可能漏检，普通代码也可能误报。它是有限正则与保守分类，不能作完全安全保证。Git/scanner 异常非零，项目输出只含类别与序号，不显示匹配值或候选文件名；不改文件/索引，也没有自定义旁路。

`python3 -B scripts/project_policy.py candidates` 读取全部未忽略的跟踪/未跟踪候选文件；显式暂存的忽略材料仍由暂存门禁阻止。`.gitignore` 只管理常见生成物，不能代替准入。本轮候选验证另清点忽略/隐藏产物，详细日志、树、哈希和执行报告放仓库外。继承宿主的日志行为受它自己的政策约束，项目工具不能承诺控制宿主全部输出。

## 验证与首次提交前置条件

设置 `TMPDIR` 到仓库外的专用 scratch，运行根 README 所列 stdlib 单元/隔离 Git 回归、foundation、候选扫描；兼容宿主环境再单独运行实际 host 集成。stub 用于故障注入，不能替代现场宿主实证。结构脚本不证明教学质量。

首次提交仍需用户确认公开 author/committer 身份、检查工程树、之后完成自我审查验收，并明确批准提交。本轮不写任何 identity 配置，不暂存/提交/创建 remote。通过 doctor 仅表示局部 hooks 可达，不能标成“已可实际提交”。本地 hooks 不构成服务端强制措施，不自动推动版本或发布；无已批准许可证不添加虚构许可证。D–G 仍见完整计划，未运行模型教学、平台发现、PLC 编译/仿真或实机。
