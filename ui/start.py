#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能启动脚本
自动检测可用的 UI 并启动
"""

import sys
import subprocess
from pathlib import Path

def check_module(module_name):
    """检查模块是否可用"""
    try:
        __import__(module_name)
        return True
    except ImportError:
        return False

def main():
    """主函数"""
    project_root = Path(__file__).parent.parent
    
    print("=" * 60)
    print("微信读书笔记导出工具 UI 启动器")
    print("=" * 60)
    print()
    
    # 检查 Web UI (Flask)
    has_flask = check_module('flask')
    
    # 检查桌面 UI (tkinter)
    has_tkinter = check_module('tkinter')
    
    print("检测结果:")
    print(f"  - Flask (Web UI): {'✓ 可用' if has_flask else '✗ 未安装'}")
    print(f"  - tkinter (桌面 UI): {'✓ 可用' if has_tkinter else '✗ 不可用'}")
    print()
    
    # 优先使用 Web UI
    if has_flask:
        print("启动 Web UI...")
        print("访问地址: http://127.0.0.1:5000")
        print("按 Ctrl+C 停止服务器\n")
        subprocess.run([sys.executable, str(project_root / "ui" / "app_web.py")])
    
    elif has_tkinter:
        print("启动桌面 UI...")
        subprocess.run([sys.executable, str(project_root / "ui" / "app.py")])
    
    else:
        print("错误: 没有可用的 UI 选项")
        print()
        print("请安装 Flask 以使用 Web UI:")
        print("  pip install flask")
        print("  或")
        print("  pip install -r requirements.txt")
        print()
        print("或者安装 tkinter 以使用桌面 UI:")
        print("  macOS: brew install python-tk")
        print("  或使用系统 Python: /usr/bin/python3 ui/app.py")
        sys.exit(1)

if __name__ == "__main__":
    main()

