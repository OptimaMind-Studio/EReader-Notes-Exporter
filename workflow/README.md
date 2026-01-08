# Guidebook 自动化流程

## 简介

`guidebook_pipeline.py` 是一个 Python 自动化脚本，用于执行完整的 guidebook 生成和导入流程：

1. **Fetch** - 调用 `wereader/fetch.py` 执行完整的数据获取流程：
   - Fetch books list（获取书籍列表）
   - Fetch bookmarks（获取书签）
   - Fetch reviews（获取点评）
   - Merge notes（合并笔记）
2. **Generate Guidebook** - 使用 LLM 生成 guidebook（逐句解释）
3. **Import to Anki** - 将 guidebook 导入到 Anki，并同步到 AnkiWeb

## 使用方法

### 处理单本书籍

```bash
# 使用书籍 ID
python workflow/guidebook_pipeline.py --book-id 3300089819

# 使用书籍名称
python workflow/guidebook_pipeline.py --book-name "极简央行课"
```

### 处理所有书籍

```bash
python workflow/guidebook_pipeline.py
```

## 前置条件

1. **Cookie 文件**：确保 `wereader/cookies.txt` 存在且有效
2. **Python 环境**：确保已安装 Python 3 和所需依赖
3. **API Key**：确保已设置 `GEMINI_API_KEY` 或 `GOOGLE_API_KEY` 环境变量
4. **Anki**：确保 Anki 正在运行，且已安装 AnkiConnect 插件

## 工作流程

### 单本书籍流程

1. Fetch 数据（书籍列表、书签、点评、合并笔记）
2. 生成 Guidebook（使用 LLM）
3. 导入到 Anki（自动创建卡组，跳过重复卡片，同步到 AnkiWeb）

### 所有书籍流程

1. Fetch 所有书籍数据（一次性）
2. 对每本书：
   - 生成 Guidebook
   - 导入到 Anki
3. 显示处理统计（成功/失败数量）

## 注意事项

- 脚本使用 `set -e`，遇到错误会立即退出
- 处理所有书籍时，如果某本书失败，会继续处理下一本
- Anki 导入会自动同步到 AnkiWeb（使用 `--sync` 选项）
- 脚本会自动跳过已存在的 guidebook 记录（基于 bookmarkId 去重）

## 输出位置

- **Fetch 输出**：`wereader/output/`
- **Guidebook 输出**：`llm/output/guidebook/`
- **Anki 卡组**：`微信读书::guidebook::{书名}`

