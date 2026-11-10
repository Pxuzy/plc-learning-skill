# plc-learning-skill

面向各品牌真实 PLC 程序与工程的学习、讲解和分析技能：把可读的 ST/SCL、梯形图（LD/LAD）、功能块图（FBD）、顺序功能图（SFC）、指令表（IL/STL）等材料拆解成可核对、可复习的学习内容，讲清条件、执行顺序、状态变化与模块交接，保留源码原样，标出证据边界。西门子、欧姆龙、倍福、台达是当前品牌资料整理方向，不限制其它品牌的可读代码分析；专有格式解析、指令语义和运行行为按产品线、格式及版本分别核验。

本仓库既是技能本体，也是它的版本管理记录。

## 目录

| 路径 | 用途 |
|---|---|
| `SKILL.md` | 技能入口：路由、硬约束、交付门槛 |
| `references/` | 按需加载的规范与模板（手册结构、代码解读、注释质量、工作流等） |
| `scripts/` | 校验与检查器（结构、模板索引、注释、代码完整性、版式） |
| `evals/` | 离线回归、合成夹具与人工行为验收清单 |
| `CHANGELOG.md` | 版本变更记录，按“未发布”维护，发布时另行确认版本 |
| `.githooks/` | 提交门禁 |
| `_backup/`、`_preview/`、`.ai/` | 本地工作数据，不进版本库 |

## 维护流程

改动前先读 `references/workflow.md` 的「技能维护与成果保护」，并按其要求把整份技能复制到目录外备份、逐文件记录 SHA-256。备份不替代提交，提交也不替代备份。

改动后跑四条维护校验（不改 PLC 程序、不覆盖既有夹具）：

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONUTF8=1 python -X utf8 -B evals/run.py
PYTHONDONTWRITEBYTECODE=1 PYTHONUTF8=1 python -X utf8 -B scripts/validate_skill.py . --strict
PYTHONDONTWRITEBYTECODE=1 PYTHONUTF8=1 python -X utf8 -B scripts/validate_template_index.py
git diff --check
```

Windows 上必须显式用 UTF-8 运行，否则默认代码页会让中文与表情样例读写报编码错，看起来像测试失败。

已知基线失败不属于本轮回归：`test_catalog.py` 与 `test_first_principles_contract.py` 的符号链接用例报 `WinError 1314`（当前账户没有创建符号链接的特权），其余数项为样例与校验器契约不一致。报告时必须把环境限制、既有问题与本轮改动分开写，不能合并成「全部通过」。

## Git 约定

- 主干分支 `main`，只做本地提交；推送、打标签、发布需要当前任务的明确授权。
- 换行统一 LF，`.gitattributes` 对 `evals/fixtures/` 关闭文本转换，保证夹具逐字节保真；换行漂移按缺陷处理。
- 一个提交只承载一类变化：规则与其配套模板、样例、测试同属一次；测试输出、压缩包、审计日志不进提交。
- 提交前用 `git status` 与 `git diff --staged` 核对范围，提交后核对 `HEAD`、文件清单与工作区干净。
- 需要回退时用 `git revert` 或从目录外备份恢复；不用 `reset --hard`、`clean -fdx` 或强制推送清理现场。

### 提交标题

```
<type>(<scope>): <中文说明>
```

`type` 取 `feat` `fix` `docs` `refactor` `chore` `merge` `perf` `release` `revert` `test` `build`（兼容既有 `ci`、`style`）；scope 只用小写英文/数字/点/连字符/下划线。标题含中文且不超过 100 字符，空行后至少一条 `- ` 分条正文。`.githooks/commit-msg` 同时检查消息隐私。

### 钩子

新克隆须在仓库根目录执行 `git config core.hooksPath .githooks` 和 `git config commit.template .gitmessage`；钩子不会随 clone 自动启用：

- `pre-commit`：扫描整个真实暂存树，拒绝私有标识/源码哈希指纹、凭据、IP、本机绝对路径、个人邮箱、二进制和本地产物；再跑严格结构、模板索引和暂存区空白检查。`git add -f` 不能豁免隐私检查。完整回归按需用 `SKILL_PRECOMMIT_FULL=1 git commit ...`。
- `commit-msg`：校验英文 type、小写 scope、中文标题、空行及分条正文，并扫描消息隐私。
- `pre-push`：扫描拟推引用的全部祖先与消息，已提交后删除的隐私也阻断；禁止删除远端引用、非快进及移动已有远端标签。

钩子会挑一个可用的 Python 3.9+；Windows 上 `python3` 常被应用商店存根占用并静默返回失败，因此不能只凭命令存在就采用。隐私门禁失败必须先修复，不得用 `--no-verify`、更换 hooksPath 或修改策略绕过。首次推送前跑 `python3 -B scripts/git_privacy_gate.py audit`，扫描包括不可达对象的本地对象库。策略只保存不可逆哈希，不存私有源码。

本地钩子无法阻止有权限者主动绕过；接入远端后须另设分支/标签保护与 CI 同等检查。只有明确授权才推送、打标签或发布。

### 版本

日常开发统一记录在 `CHANGELOG.md` 的“未发布”，不自动升版。仅在用户确认发布时确定本技能的发布版本；模板格式版本按模板索引独立维护，不与技能发布版本混用。

## 边界

这是只读的学习与分析技能：不改 PLC 程序、不下载、不强制 I/O、不旁路保护、不替代实机验证。资料不足时明确标成未知或假设，不补造调用关系、工艺意图与运行结果。
