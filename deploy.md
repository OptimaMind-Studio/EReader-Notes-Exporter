# 部署指南

## 快速开始

### 1. 创建并激活虚拟环境

```bash
python -m venv .venv
source .venv/bin/activate
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 设置 Cookie 文件

从浏览器导出微信读书 Cookie，保存到 `wereader/cookies.txt`

### 4. 设置 Gemini API Key（LLM 功能需要）

```bash
export GEMINI_API_KEY='your_api_key'
# 或
export GOOGLE_API_KEY='your_api_key'
```

### 5. 运行主程序

```bash
# 处理所有书籍
python wereader/main.py

# 处理特定书籍
python wereader/main.py --book-id 3300089819
```

## 单独运行脚本

### 获取书籍列表

```bash
python wereader/scripts/fetch_books.py --cookie wereader/cookies.txt
python wereader/scripts/fetch_books.py --cookie wereader/cookies.txt --book-id 3300089819
```

### 获取书签

```bash
python wereader/scripts/fetch_bookmarks.py --cookie wereader/cookies.txt
python wereader/scripts/fetch_bookmarks.py --cookie wereader/cookies.txt --book-id 3300089819
```

### 获取点评

```bash
python wereader/scripts/fetch_reviews.py --cookie wereader/cookies.txt
python wereader/scripts/fetch_reviews.py --cookie wereader/cookies.txt --book-id 3300089819
```

### 合并笔记

```bash
python wereader/scripts/merge_notes.py
python wereader/scripts/merge_notes.py --book-id 3300089819
```

## LLM 功能

### 概念提取

```bash
# 使用 bookID
python llm/extract_concepts.py --book-id 3300089819
python llm/extract_concepts.py --book-id 3300089819 --output llm/output/concepts/book_concepts.csv

# 使用书名
python llm/extract_concepts.py --title "书名"
```

### 生成大纲

```bash
# 使用 bookID
python llm/generate_outline.py --book-id 3300089819
python llm/generate_outline.py --book-id 3300089819 --output llm/output/outlines/book_outline.md

# 使用书名
python llm/generate_outline.py --title "书名"
python llm/generate_outline.py --title "书名" --role 学习者
```

### 生成学习指南

```bash
# 使用书名和章节名
python llm/generate_guidebook.py --title "书名" --chapter "章节名"

# 使用 bookID 和章节名
python llm/generate_guidebook.py --book-id 3300089819 --chapter "第一章"

# 处理整本书
python llm/generate_guidebook.py --book-id 3300089819
python llm/generate_guidebook.py --title "书名"
```

## Anki 导入

```bash
python anki/import_guidebook_to_anki.py --book-id 3300089819

python anki/import_guidebook_to_anki.py --book-id 3300089819 --sync # 强制同步到server
```
