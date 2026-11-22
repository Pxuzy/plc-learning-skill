# 生成后校验：执行 → 修正 → 重验

## 适用范围

局部 ST/SCL 讲解、完整手册和教学重建生成文档后，实际运行已有校验器。先写完整草稿，再检查；纯事实短答不套文档流程。检查不修改 PLC 源程序，不替代注释含义与教学因果的语义审查。

命令从技能根目录执行，文档及源文件可用带引号的绝对路径。原始源码独立保存，保留换行、缩进、原注释和末行状态，不能从生成稿反推原码。

Python 3.9+；严格 Markdown 检查需 `scripts/requirements-markdown.txt` 的解析依赖。缺少时按环境许可安装：

```bash
python3 -m pip install -r scripts/requirements-markdown.txt
```

## 纯源码 Markdown 导出与后续任务

适用 SMC2 定位器的 `--output-md` 路线在发布文件前完成：请求分支集合对账、源码逐字符回读比较（包含空白、CRLF、末行换行）、原始声明保留、中文变量表的行序/字段和实际渲染文字核对，以及既有严格 Markdown 渲染检查。围栏自动避开源码内同类分隔符；技术摘要只作辅助，不能替代源码比较。输入缺失或导出失败时不发布貌似完整的文件，不覆盖已有底稿。

只有实际完成的检查可标为通过；变量未转换、环境缺少依赖、编译/仿真/实机未执行分别写明。格式检查未执行或失败，不能把导出称为已验证成功；按环境许可补齐现有依赖后重试，不放宽检查器。

导出校验不能代替后续讲解的校验。模型按用户原请求从底稿继续讲解/分析/修改，适用时仍执行下面的源码保真、教学注释、五部分结构和 Markdown 检查；纯提取不强套教学尾注或讲解模板，原件和后续产物分别保存。

## 局部 ST/SCL：依次执行三项

```bash
python3 scripts/check_local_explanation.py explanation.md --source original.st
python3 scripts/check_plc_comments.py explanation.md
python3 scripts/check_markdown_format.py explanation.md --strict
```

分别检查五部分结构及源码保真、默认逐行尾注和已知低价值形式、Markdown 真实渲染。每条非空代码行（含条件续行和结构闭合行）都须尾注；只豁免空白、纯注释和未闭合块注释内部行。原行字符与作者注释保留，只在末尾追加；剥离本轮新增尾注后与独立原码逐字符一致。

只有当次明确要求原样源码或仅归档，才给支持该选项的前两项加 `--original-source`；不能因为漏注被拒而改模式刷绿。

## 手册与教学重建：按适用项执行

```bash
python3 scripts/validate_handbook.py handbook.md
python3 scripts/check_plc_comments.py handbook.md
python3 scripts/check_markdown_format.py handbook.md --strict
```

有匹配独立源文件的 manifest 时，再做源码完整性对账：

```bash
python3 scripts/check_code_integrity.py --manifest manifest.json --doc handbook.md
```

manifest 的生成见 [手册工具链](handbook-build-toolchain.md)。缺源或缺 manifest 列为未对账，不能用生成器自己的计划证明全部覆盖。最终完整稿按 [学习流程](workflow.md) 使用既有 `--final` 和 `--comment-review` 门槛；未做逐块语义审查不伪造记录。

## 反馈与交付

1. 保存完整草稿，**执行**全部适用命令，读取每条命令实际退出码和报错行。
2. 漏注补业务短句，字段缺失补原字段，格式错误修排版；源码变化恢复原行。只修生成稿，不改源程序或检查器来消除报错。
3. 修改后**重新运行**全部适用检查，直到确定性错误清零。任何正文、尾注或输入变更后，旧结果不能代表当前文件。
4. 在既有 `**验证状态**` 字段写实际执行项目、结果与待审项，不增加教学栏目。所有适用脚本退出码为 0 才称“机械校验通过”；编译、仿真、实机和语义正确性另报。

无文件/终端工具或依赖无法取得时，交付标“未校验草稿”，列明未执行项目和原因；人工目测、模型自述不能代替脚本。保留失败事实，不称校验完成。

## 图形语言与非 ST 方言

LAD/FBD 保留原图或原生拓扑，逐网络核对接点、线圈和连接；不伪写 ST，不运行 ST 专用局部校验。IL/STL、SFC 按实际方言核对，不用 ST 全绿替代平台语义证明。

共用 Markdown 校验可执行 `python3 scripts/check_markdown_format.py explanation.md --strict`，另列图形覆盖及方言检查的实际状态。混合语言按单元分别判定；归档按 [源码归档](source-archive.md) 对账，不套教学尾注。
