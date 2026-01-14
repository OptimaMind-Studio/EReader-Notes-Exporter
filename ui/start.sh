#!/bin/bash
# 启动 UI 应用（优先使用 Web UI）

cd "$(dirname "$0")/.."

# 检查是否有 tkinter
if python3 -c "import tkinter" 2>/dev/null; then
    echo "使用桌面 UI..."
    python3 ui/app.py
else
    echo "检测到 tkinter 不可用，使用 Web UI..."
    echo "如果未安装 Flask，请先运行: pip install flask"
    python3 ui/app_web.py
fi

