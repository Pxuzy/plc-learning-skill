#!/bin/sh
# 失败即阻断，不接受缺少解释器时跳过。
set -eu
cd "$(git rev-parse --show-toplevel)"
PY=""
for candidate in python3 python py; do
    if command -v "$candidate" >/dev/null 2>&1 &&
       "$candidate" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)" >/dev/null 2>&1; then
        PY="$candidate"
        break
    fi
done
if [ -z "$PY" ]; then
    printf '%s\n' 'Git 门禁拒绝：需要可用的 Python 3.9+。' >&2
    exit 1
fi
export PYTHONDONTWRITEBYTECODE=1 PYTHONUTF8=1
