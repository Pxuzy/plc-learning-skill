#!/usr/bin/env python3
"""表情门禁：完整手册所有标题都须带表情；普通文档不拦。"""
import subprocess, sys, tempfile
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts' / 'check_document_layout.py'

BODY = """
## 一、工程概览 🏭

说明。

### M01 启动许可 🔍

#### 1. 功能定位与执行条件 🔹

条件与因果。

#### 2. 源码 🔹

```st
IF xStart THEN
    xRun := TRUE;
END_IF;
```

#### 3. 代码块整体讲解 🔹

因为请求是瞬时输入，所以用状态保存结果。

#### 4. 形象示例 🧪

| 扫描 | 输入 | 结果 |
|---|---|---|
| 1 | xStart=TRUE | xRun=TRUE |

#### 5. 程序交互与段间交接 🔗

写入 xRun，供下游读取。
"""


def run(text):
    with tempfile.NamedTemporaryFile('w', suffix='.md', delete=False, encoding='utf-8') as f:
        f.write(text)
        p = f.name
    return subprocess.run([sys.executable, '-B', str(SCRIPT), p],
                          capture_output=True, text=True)


class TitleEmojiGateTests(unittest.TestCase):
    def test_handbook_all_headings_emoji_passes(self):
        r = run('工程：测试\n讲解深度：代码深度\n' + BODY)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn('缺少表情', r.stdout + r.stderr)

    def test_module_heading_without_emoji_fails(self):
        doc = '工程：测试\n讲解深度：代码深度\n' + BODY.replace('### M01 启动许可 🔍', '### M01 启动许可')
        r = run(doc)
        self.assertNotEqual(r.returncode, 0, r.stdout)
        self.assertIn('缺少表情', r.stdout)

    def test_non_handbook_document_is_not_gated(self):
        r = run(BODY.replace('### M01 启动许可 🔍', '### M01 启动许可'))
        self.assertNotIn('缺少表情', r.stdout + r.stderr)


if __name__ == '__main__':
    unittest.main(verbosity=2)
