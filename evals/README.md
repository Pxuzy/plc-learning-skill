# Maintainer Checks

## Synthetic fixtures

The [synthetic PLC fixtures](fixtures/README.md) are source-only cases for future Skill evaluation. They are not loaded during runtime invocation, are not certified compilable or safe, and do not represent vendor project formats.

These checks are optional maintenance aids and are not part of ordinary Skill invocation or explanation. Run from the repository root:

```sh
python3 evals/check_foundation.py
```

The checker uses only the Python standard library and validates required files, local Markdown links, metadata basics, and runtime wording. Passing it does not prove explanation quality, platform behavior, host discovery compatibility, or Python-free target compatibility.

## Manual no-Python walkthrough

Use plain ST and Ladder excerpts pasted directly into an invocation. Do not provide a vendor project or run a script. Ask for a detailed beginner explanation and manually check that each response:

1. Limits claims to the visible excerpt and preserves its source characters in the teaching copy.
2. Adds `AI:` to each feasible non-empty source line, retains original comments, and explains any omission.
3. Explains the block's role, condition, read/write effects, and execution causality.
4. Distinguishes facts, paper-trace assumptions, inference, and unknowns.
5. Includes a separate Critical review with evidence limits and honest validation status.

For the ST case, use a short `IF` with an assignment and `END_IF`. In addition to the checks above, verify that the explanation gives a concrete labeled paper trace when initial values can be grounded, and identifies what is missing if no grounded trace is possible.

### Vendor-neutral Ladder walkthrough

Paste this small vendor-neutral representation and state that its bracket/coil notation is an abstract input for this walkthrough only:

```text
Rung 1:
  --[ Start ]--+--[ Permit ]--+--( Run )
               +--[ Bypass ]--+
```

Check that the answer preserves the visible layout and relationships, explains the series `Start` path and the parallel `Permit`/`Bypass` paths in represented order, and identifies visible condition reads and the `Run` write. Check that series/parallel relationships and branch joins are described only when visually clear, and that cropped, flattened, or ambiguous layout or undocumented instruction meaning remains unknown. The response must not invent an unseen IDE/network or vendor-specific semantics. Require a labeled paper trace when initial values and visible semantics can be grounded; check branch decisions, resulting writes, and retained values. Otherwise, require the answer to name the missing values or semantics that prevent a grounded trace. No runtime result may be claimed. Check source-to-teaching-copy correspondence and that any annotation format does not obscure the rung layout.

Then ask a brief factual question and check that the response stays brief and does not force the full teaching format. These walkthroughs need no Python, scripts, shell, packages, network, or vendor adapter. They are manual acceptance checks, not vendor or runtime certification. The Ladder case is specified here but has not been model-executed; record a fresh walkthrough and its observed result separately before claiming that acceptance check passed.

## 第一阶段维护实现验证

治理回归使用 Python 标准库，先设置 `TMPDIR` 到仓库外专用 scratch；运行 `python3 -B -m unittest discover -s evals/tests -v`。测试只在临时 Git 仓库暂存/提交，使用公开 example 域的合成身份；不对本项目执行暂存/提交。覆盖暂存 blob、消息与身份、材料分类、安装/doctor/恢复和真实隔离提交。

`evals/tests/test_hook_chain.py` 是宿主契约 stub 故障注入。兼容宿主环境下另运行 `python3 -B evals/tests/host_integration.py`，测试现场继承宿主的隔离真实提交与 hook trace，失败不降级为 standalone。无宿主的环境不把此项标为已验证。`scripts/project_policy.py candidates` 无需暂存即可扫描全部未忽略候选。

上述是 A/B/C 实现级验证。详细 RED/GREEN 日志、文件哈希、现场链记录及独立执行正文报告留在仓库外；本轮完成后等待用户检查实际工程树，随后才开始自我审查验收。未执行上文模型 walkthrough、D–G、平台真实发现或 PLC 编译/运行，不将本节测试通过升级为教学验收。
