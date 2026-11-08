import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = ROOT / 'scripts' / 'validate_handbook.py'

SOURCE = '''PROGRAM Demo
VAR
    Enable : BOOL := TRUE;
    Count : INT := 0;
END_VAR

IF Enable THEN
    Count := Count + 1;
END_IF;
END_PROGRAM
'''


def handbook(source=SOURCE):
    return f'''# Demo 讲解

## 关键变量

| 变量 | 数据类型 | 方向 | 含义 | 谁写谁读 | 证据等级 |
|---|---|---|---|---|---|
| `Enable` | `BOOL` | 内部 | 启用条件 | 代码读取 | 源码事实 |

## 1. 功能定位与执行条件

说明。

## 2. 源码

```st
{source}
```

## 3. 代码块整体讲解

### 处理过程
说明。

### 关键逻辑
说明。

### 写法好处
本片段不足以确认。

### 状态变化
说明。

## 4. 形象示例

纸面轨迹。

## 5. 程序交互与段间交接

未知。

## 批判性审查

暂无已证实问题。

### 验证状态

仅执行结构检查。
'''


class HandbookValidatorTests(unittest.TestCase):
    def run_validator(self, source=SOURCE, document=None):
        with tempfile.TemporaryDirectory(prefix='plc-handbook-test-') as temporary:
            root = Path(temporary)
            source_path = root / 'input.st'
            handbook_path = root / 'handbook.md'
            source_path.write_text(source, encoding='utf-8')
            handbook_path.write_text(document if document is not None else handbook(source), encoding='utf-8')
            return subprocess.run(
                [sys.executable, '-B', VALIDATOR, '--source', source_path, '--handbook', handbook_path],
                cwd=ROOT,
                capture_output=True,
                timeout=30,
            )

    def test_accepts_complete_synthetic_handbook(self):
        result = self.run_validator()
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))

    def test_rejects_handbook_with_incomplete_source_without_echoing_source(self):
        incomplete = handbook(SOURCE.replace('END_IF;\n', ''))
        result = self.run_validator(document=incomplete)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b'source-coverage', result.stderr)
        self.assertNotIn(b'Count := Count + 1;', result.stderr)

    def test_rejects_wrong_section_order(self):
        document = handbook().replace(
            '## 4. 形象示例\n\n纸面轨迹。\n\n## 5. 程序交互与段间交接',
            '## 5. 程序交互与段间交接\n\n未知。\n\n## 4. 形象示例',
            1,
        )
        result = self.run_validator(document=document)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b'section-order', result.stderr)


if __name__ == '__main__':
    unittest.main()
