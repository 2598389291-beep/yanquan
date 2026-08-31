#!/usr/bin/env bash
cd /Users/hh/Documents/codex/yanquan/miniapp/dist-h5 || exit 1
exec /usr/bin/python3 -m http.server 8090
