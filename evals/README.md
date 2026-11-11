# 离线回归

`evals/run.py` 逐个执行本地 `test_*.py`，不调用模型、不读凭据、不联网。

```bash
python3 -B evals/run.py --dry-run   # 只列出将运行的测试
python3 -B evals/run.py             # 全部跑一遍
```

`cases.md` 是人工行为验收清单，不由 runner 自动执行。

模式 B 的局部讲解使用 `scripts/check_local_explanation.py <文档.md> --source <原始.st>`；检查器比较源码围栏按序拼接后的文本与输入文件，不归一空白或 CRLF/LF。若源文件末行没有换行，在最后一个源码围栏闭合行后紧接 `<!-- source-eof: none -->`，只排除 Markdown 围栏边界带来的一个换行。检查通过仍会打印待审语义提示。`evals/check_local_behavior_artifacts.py` 用于核验冻结清单、请求和候选哈希的一致性；不采样、不联网、不读凭据。

深讲契约测试只断言六槽位、证据缺口与坏最小 Markdown 拒绝，样例写在该测试文件内，不依赖任何用户工程源码或夹具目录；标签齐全不等于讲解正确，契约通过也不等于任意模型实际生成质量合格。评估教学效果须用同一题目实际生成并人工审阅必要性推导、代码覆盖和跨扫描反例。

教学交付默认运行 `python3 -B scripts/check_plc_comments.py <文档.md>`（默认逐行；`--require-every-line` 为兼容别名），并独立记录普通质量门禁结果。`--legacy-selective` 只用于历史夹具的选择性审查，`--original-source` 只在当次明确要求原样源码时使用。缺注释、低价值与重复错误分开核对；默认局部 B 交付追加注释版，新生成 ST/SCL 文档另跑 `--require-condition-ai`；长手册也可通过 `validate_handbook.py --require-condition-ai` 启用。回归夹具均为合成片段，不依赖用户归档。

离线脚本只使用 Python 标准库；不得因 Python 版本差异跳过、降级或改写校验结论。工具通过不表示格式解析或产品支持，也不代表 PLC 语义、编译或现场行为已验证。

人工行为验收还包含两类固定案例：厂商中立 Ladder 走查按可见图面分别记录串联路径、并联路径与分支汇合，裁切或歧义布局标为未知，不重建不可见的 IDE 网络；变量证据按具体变量及声明/作用域逐项记录，不把多个变量合并成“混合方向”。

测试分组：

| 文件 | 覆盖 |
|---|---|
| `test_audit_contracts.py` | 临时源文件→manifest→推荐 ST/FB 成品→源码对账/注释/final；首网前声明、来源邻接、局部状态、只读、词法扫描、围栏正文与 Mermaid 正反例 |
| `test_handbook.py` | 手册交付契约、参考文件精简、用例存在 |
| `test_first_principles_contract.py` | A/B 到手册/深讲/教学的必要性推导；短 IF 保持、互锁复位、意图未知、纯归档、按歧义暂停的源码确认门禁及缺失变异；仅静态内容契约，不证明会话表现 |
- `test_block_layout.py`：关键变量前置、块级正文与缺项/旧列表反向用例。
| `test_handbook_validator.py` | 按适用性校验、模板组合、目录锚点、源码与安全边界正反例 |
| `test_comment_quality.py` | 全文 PLC 行内覆盖、复述/空话/重复、字符串边界、库内正例和最终逐块审查记录；严格逐行模式覆盖闭合行、空尾注、注释后代码及跨行条件/调用；不证明任意业务语义 |
| `test_template_index.py` | 模板 ID、版本、组合对称性与路由正反例 |
| `test_code_integrity.py` | 代码块与源程序逐行对账，拒绝整块交换和同单元分片倒序 |
| `test_make_manifest.py` / `test_diff_export.py` | 源清单与版本差异 |
| `test_smc2_archive.py` | SMC2 归档清点与路径穿越防护 |
| `test_survey_program.py` | 程序统计与跨单元写入 |
| `test_st_rendering.py` | CommonMark 围栏边界、嵌套短示例、闭合围栏独立成行与实际行号诊断 |
| `test_reference_flatness.py` | 参考文件均被索引、无悬空链接 |
| `test_offline_runner.py` | runner 只跑本地测试 |
| `test_local_explanation_contract.py` | B 两份骨架填实结果、字段/表列、执行行数、交接与结束标记正反例 |
| `test_local_explanation_cli.py` | B 专用 CLI 子进程退出码、逐字符源码、EOF 标记、范围覆盖与待审输出 |
| `test_local_behavior_artifacts.py` | 行为批次冻结候选、请求副本与哈希不一致拒绝；本地固定数据，不采样 |
| `test_long_text_delivery.py` | 长文本自动切分、连续全覆盖、批次状态、最终合并与提前停止负例 |
| `test_long_text_quality_gate.py` | 长文逐段语义验收、覆盖率与讲解质量双状态、只贴源码冒充讲解的失败信号 |
| `test_git_privacy_gate.py` | 临时 Git 仓库验证暂存树隐私、消息样式、祖先扫描和推送边界 |
| `test_commit_message_hook.py` | 临时仓库中 repo-local commit-msg 格式钩子的合法/非法提交集成测试 |
| `test_local_teaching_review.py` | TON 教学假设下定时/状态轨迹重算及待人工审阅的零基础覆盖规则 |
