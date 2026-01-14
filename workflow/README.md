# Workflow 自动化流程

## Concepts Pipeline

Concepts 自动化流程：fetch -> extract concepts

### 用法

```bash
# 处理所有书籍
python workflow/concepts_pipeline.py

# 处理指定书籍ID
python workflow/concepts_pipeline.py --book-id 3300089819

# 处理指定书名
python workflow/concepts_pipeline.py --book-name "极简央行课"
```

### 流程说明

1. **Fetch 数据**: 执行 `wereader/fetch.py` 完整流程
   - Fetch books list
   - Fetch bookmarks
   - Fetch reviews
   - Merge notes

2. **提取概念**: 执行 `llm/scripts/extract_concepts.py`
   - 从笔记中提取概念词
   - 生成概念定义
   - 保存到 `llm/output/concepts/`

## Guidebook Pipeline

Guidebook 自动化流程：fetch -> generate guidebook -> import to anki

### 用法

```bash
# 处理所有书籍
python workflow/guidebook_pipeline.py

# 处理指定书籍ID
python workflow/guidebook_pipeline.py --book-id 3300089819

# 处理指定书名
python workflow/guidebook_pipeline.py --book-name "极简央行课"
```

### 流程说明

1. **Fetch 数据**: 执行 `wereader/fetch.py` 完整流程
2. **生成 Guidebook**: 执行 `llm/scripts/generate_guidebook.py`
3. **导入 Anki**: 执行 `anki/scripts/import_guidebook_to_anki.py`（自动同步到 AnkiWeb）

## 注意事项

- 所有 pipeline 都需要 Cookie 文件（`wereader/cookies.txt`）
- Concepts pipeline 需要设置 `GEMINI_API_KEY` 或 `GOOGLE_API_KEY` 环境变量
- Guidebook pipeline 需要设置 `GEMINI_API_KEY` 或 `GOOGLE_API_KEY` 环境变量，并且需要 Anki 和 AnkiConnect 运行
