#!/usr/bin/env bash
# gemini-handoff のインストール。引数はそのまま install.py に渡す (--uninstall / --threshold N)
set -euo pipefail
exec python3 "$(cd "$(dirname "$0")" && pwd)/install.py" "$@"
