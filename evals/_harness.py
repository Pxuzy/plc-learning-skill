#!/usr/bin/env python3
"""测试用的进程内调用器。

直接 import 脚本模块并调用它的 main()，不另起子进程：
退出码取返回值或 SystemExit，stdout/stderr 用重定向抓下来。
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import sys
from pathlib import Path
from typing import NamedTuple

_LOADED: dict[Path, object] = {}


class Result(NamedTuple):
    returncode: int
    stdout: str
    stderr: str


def load(script: Path):
    script = Path(script).resolve()
    if script not in _LOADED:
        spec = importlib.util.spec_from_file_location(f"plcscript_{script.stem}", script)
        assert spec and spec.loader, f"无法加载 {script}"
        mod = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = mod
        spec.loader.exec_module(mod)
        _LOADED[script] = mod
    return _LOADED[script]


def run(script: Path, *args: str) -> Result:
    """按脚本名调用 main()；脚本从 sys.argv 取参也能正常工作。"""
    mod = load(script)
    out, err = io.StringIO(), io.StringIO()
    saved = sys.argv
    sys.argv = [str(script), *map(str, args)]
    code: object = 0
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = mod.main()
            except SystemExit as exc:
                # 与命令行一致：带字符串的 SystemExit 会把消息写进 stderr
                if isinstance(exc.code, str):
                    print(exc.code, file=sys.stderr)
                    code = 1
                else:
                    code = exc.code if exc.code is not None else 0
    finally:
        sys.argv = saved
    rc = code if isinstance(code, int) else 1
    return Result(rc, out.getvalue(), err.getvalue())
