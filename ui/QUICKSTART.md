# 快速开始

## 问题：tkinter 不可用？

如果遇到 `ModuleNotFoundError: No module named '_tkinter'` 错误，请使用 Web UI。

## 解决方案

### 方案 1: 使用 Web UI（推荐）

1. **安装 Flask**:
   ```bash
   pip install flask
   ```

2. **启动 Web UI**:
   ```bash
   python3 ui/app_web.py
   ```
   
   或使用启动脚本：
   ```bash
   ./ui/start_web.sh
   ```

3. **访问界面**: 浏览器会自动打开 `http://127.0.0.1:5000`

### 方案 2: 使用智能启动脚本

```bash
python3 ui/start.py
```

这个脚本会自动检测可用的 UI 并启动。

### 方案 3: 安装 tkinter（仅桌面 UI）

**macOS**:
```bash
brew install python-tk
```

或使用系统 Python（通常包含 tkinter）:
```bash
/usr/bin/python3 ui/app.py
```

## 推荐方案

**推荐使用 Web UI**，因为：
- ✅ 无需安装额外的系统依赖
- ✅ 跨平台兼容性好
- ✅ 界面更现代美观
- ✅ 可以在任何设备上通过浏览器访问

只需运行：
```bash
pip install flask
python3 ui/app_web.py
```

