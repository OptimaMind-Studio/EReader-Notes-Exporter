#!/bin/bash
# 快速启动 Web UI

echo "正在检查 Flask..."
if ! python3 -c "import flask" 2>/dev/null; then
    echo "Flask 未安装，正在安装..."
    pip install flask
fi

echo "启动 Web UI..."
python3 ui/app_web.py
