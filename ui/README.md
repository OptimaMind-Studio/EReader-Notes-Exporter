# UI 使用说明

## 启动方式

### Web UI（推荐，无需 tkinter）

```bash
python3 ui/app_web.py
```

或者使用启动脚本：

```bash
./ui/start_web.sh
```

启动后会自动在浏览器中打开 `http://127.0.0.1:5000`

**首次使用需要安装 Flask：**
```bash
pip install flask
# 或
pip install -r requirements.txt
```

### 桌面 UI（需要 tkinter）

```bash
python ui/app.py
```

**注意**: macOS 上使用 Homebrew 安装的 Python 可能没有 tkinter，如果遇到 `ModuleNotFoundError: No module named '_tkinter'` 错误，请使用 Web UI。

**macOS 上安装 tkinter 的方法：**
```bash
# 使用系统 Python（通常包含 tkinter）
/usr/bin/python3 ui/app.py

# 或者安装 Python-tk
brew install python-tk
```

## 功能说明

### Cookie 设置
- **浏览**: 选择 Cookie 文件位置
- **编辑 Cookie**: 打开 Cookie 文件编辑器，可以直接编辑 Cookie 内容

### WeRead 数据获取
- **获取书籍列表**: 从微信读书获取所有书籍列表
- **获取书签和点评**: 获取书籍的书签（划线笔记）和点评，并合并为笔记

### LLM 处理
- **提取概念**: 从笔记中提取概念词并生成定义
- **生成大纲**: 生成学习大纲
- **生成 Guidebook**: 生成逐句解释的学习指南
- **完整 LLM 流程**: 依次执行概念提取、大纲生成和 Guidebook 生成

### 自动化流程
- **Guidebook 完整流程**: 执行完整的 Guidebook 流程（Fetch + Generate Guidebook + Import to Anki）

### 书籍选择
- **书籍ID**: 输入书籍ID（可选）
- **或书名**: 输入书名（可选）
- 如果不输入，某些功能会处理所有书籍

## 注意事项

1. **Cookie 文件**: 首次使用前需要设置 Cookie 文件路径
2. **API Key**: LLM 功能需要设置 `GEMINI_API_KEY` 或 `GOOGLE_API_KEY` 环境变量
3. **书籍选择**: 大部分 LLM 功能需要指定书籍ID或书名
4. **日志输出**: 所有操作的日志会实时显示在日志输出区域

## 数据存储位置

所有数据存储在原有位置：
- 书籍列表: `wereader/output/fetch_notebooks_output.csv`
- 书签: `wereader/output/bookmarks/`
- 点评: `wereader/output/reviews/`
- 合并笔记: `wereader/output/notes/`
- 概念: `llm/output/concepts/`
- 大纲: `llm/output/outlines/`
- Guidebook: `llm/output/guidebook/`

## 故障排除

### Web UI 无法启动
- 确保已安装 Flask: `pip install flask`
- 检查端口 5000 是否被占用
- 查看终端错误信息

### 桌面 UI tkinter 错误
- 使用 Web UI 替代（推荐）
- 或安装系统 Python（通常包含 tkinter）
- 或安装 python-tk: `brew install python-tk`
