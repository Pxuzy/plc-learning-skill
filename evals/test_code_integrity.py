#!/usr/bin/env python3
"""check_code_integrity.py 的正反例自测（不依赖真实 PLC 工程）。"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _harness as harness  # noqa: E402

HERE = Path(__file__).resolve().parent
CHECKER = HERE.parent / "scripts" / "check_code_integrity.py"

SOURCE = """// 导出文件头
[MainProgram]
// NETWORK 1
IF bStart THEN
    nStep := 10;
END_IF;
// NETWORK 2
IF nStep = 10 AND bReady THEN
    nStep := 20;
END_IF;
// NETWORK 3
IF nStep = 20 THEN
    bClamp := TRUE;
END_IF;
// NETWORK 4
nCount := nCount + 1;
// 文件尾
// 说明
// 说明
// 说明
""".splitlines()
SOURCE[4] += "  "  # Exercise source whitespace without whitespace errors in this file.

UNITS = [
    {"id": "U1", "pou": "MainProgram", "kind": "network", "start": 3, "end": 6},
    {"id": "U2", "pou": "MainProgram", "kind": "network", "start": 7, "end": 10},
    {"id": "U3", "pou": "MainProgram", "kind": "network", "start": 11, "end": 14},
    {"id": "U4", "pou": "MainProgram", "kind": "network", "start": 15, "end": 16},
]


def block(start: int, end: int, comment: bool = False, file: str | None = None) -> str:
    ann = f"<!-- src: {file + ':' if file else ''}{start}-{end} -->"
    body = []
    for line in SOURCE[start - 1 : end]:
        if comment and line.strip() and not line.strip().startswith("//"):
            line = line + " // 中文说明"
        body.append(line)
    return f"{ann}\n```st\n" + "\n".join(body) + "\n```\n"


def good_doc(comment: bool = False) -> str:
    return "# 文档\n\n" + "\n".join(block(u["start"], u["end"], comment) for u in UNITS)


def run(tmp: Path, doc_text: str, units=None, extra=None, cli: list[str] | None = None) -> tuple[int, str]:
    (tmp / "export.txt").write_text("\n".join(SOURCE) + "\n", encoding="utf-8")
    manifest = {
        "source": "export.txt",
        "exclude": [
            {"start": 1, "end": 2, "reason": "文件头"},
            {"start": 17, "end": 20, "reason": "文件尾"},
        ],
        "units": units if units is not None else UNITS,
    }
    if extra:
        manifest.update(extra)
    (tmp / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    (tmp / "doc.md").write_text(doc_text, encoding="utf-8")
    r = harness.run(
        CHECKER,
        "--manifest",
        str(tmp / "manifest.json"),
        "--doc",
        str(tmp / "doc.md"),
        *(cli or []),
    )
    return r.returncode, r.stdout + r.stderr


CASES = []


def case(name, expect_code, keyword, doc=None, units=None, cli=None):
    CASES.append((name, expect_code, keyword, doc, units, cli))


case("全部对齐", 0, "通过", good_doc())
case("行尾追加注释", 0, "通过", good_doc(comment=True))
case("同一单元正序分片允许通过", 0, "通过", "# 文档\n\n" + block(3, 4) + block(5, 6) + "\n".join(block(u["start"], u["end"]) for u in UNITS[1:]))
case("清单登记次序不替代源行次序", 0, "通过", good_doc(), list(reversed(UNITS)))
case("交换完整源码块不得冒称顺序保真", 1, "源码顺序", "# 文档\n\n" + "\n".join(block(u["start"], u["end"]) for u in (UNITS[1], UNITS[0], UNITS[2], UNITS[3])))
case("同一单元分片倒序不得通过", 1, "源码顺序", "# 文档\n\n" + block(5, 6) + block(3, 4) + "\n".join(block(u["start"], u["end"]) for u in UNITS[1:]))
case("缺一个单元", 1, "缺失", good_doc().replace(block(11, 14), ""))
case("同一段重复引用", 1, "重复", good_doc() + block(7, 10))
case("改写一行", 1, "改写", good_doc().replace("nStep := 20;", "nStep := 30;"))
case("未标注代码块", 1, "未归属", good_doc() + "```st\nnCount := 0;\n```\n")
truncated = block(3, 6).splitlines()
case("截断代码块", 1, "只贴了前", good_doc().replace(block(3, 6), "\n".join(truncated[:4]) + "\n```\n"))
case(
    "清单有缺口",
    1,
    "清单未覆盖",
    good_doc(),
    [UNITS[0], {**UNITS[1], "start": 8}, UNITS[2], UNITS[3]],
)
case(
    "清单区间重叠",
    1,
    "源行重复归属",
    good_doc(),
    [UNITS[0], {**UNITS[1], "start": 6}, UNITS[2], UNITS[3]],
)
case("清单跨多个单元", 1, "跨了多个单元", good_doc().replace(block(3, 6), block(3, 7)))
case(
    "允许未覆盖",
    0,
    "允许未覆盖",
    block(3, 6),
    None,
    ["--allow-uncovered", "U2,U3,U4"],
)
case("当前批次范围", 0, "校验范围：U1", block(3, 6), None, ["--only-units", "U1"])
case("最终拒绝伪代码", 1, "伪代码块", "<!-- src: none -->\n```st\n示意代码\n```\n", None, ["--final"])
for language in ("Pascal", "ST", "SCL", "Structured-Text", "structured_text", "iecst", "FB"):
    case(f"别名 {language} 源文完整", 0, "通过", good_doc().replace("```st", "```" + language))
    case(f"别名 {language} 仍参与对账", 1, "源「", good_doc().replace("```st", "```" + language).replace("nStep := 10;", "nStep := 99;"))
case("波浪围栏源文完整", 0, "通过", good_doc().replace("```st", "~~~ST").replace("```", "~~~"))
case("波浪围栏仍参与对账", 1, "源「", good_doc().replace("```st", "~~~ST").replace("```", "~~~").replace("nStep := 10;", "nStep := 99;"))
case("四反引号源文完整", 0, "通过", good_doc().replace("```", "````"))
case("四反引号仍参与对账", 1, "源「", good_doc().replace("```", "````").replace("nStep := 10;", "nStep := 99;"))
case("原有注释不可删除", 1, "源「", good_doc().replace("// NETWORK 1", "// removed"))
case("源尾空白不可删除", 1, "源「", good_doc().replace("nStep := 10;  \n", "nStep := 10;\n"))


def main() -> int:
    failed = 0
    with tempfile.TemporaryDirectory() as td:
        for i, (name, want, kw, doc, units, cli) in enumerate(CASES, 1):
            tmp = Path(td) / f"c{i}"
            tmp.mkdir()
            code, out = run(tmp, doc if doc is not None else good_doc(), units, cli=cli)
            ok = code == want and kw in out
            print(f"{'PASS' if ok else 'FAIL'}  {name}: exit={code} 期待={want} 关键字={kw}")
            if not ok:
                failed += 1
                print("  ---- 输出 ----")
                print("  " + out.replace("\n", "\n  ")[:1500])
    print(f"\n{len(CASES) - failed}/{len(CASES)} 通过")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
