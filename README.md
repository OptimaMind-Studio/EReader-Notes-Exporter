# 微信读书笔记导出工具

用于导出微信读书（WeRead）笔记数据的 Python 工具集，支持批量导出书籍列表、书签（划线）、评论（想法），并合并为统一的笔记文件。

## 功能特性

- 📚 导出所有书籍列表及阅读进度
- 🔖 批量导出每本书的书签（划线）
- 💬 批量导出每本书的评论（想法）
- 📝 合并书签和评论为统一的笔记文件
- 📊 支持 CSV 格式导出

## 安装

```bash
pip install -r requirements.txt
```

## 配置

### Cookie 文件准备

1. 在浏览器中登录微信读书网页版（https://weread.qq.com）
2. 使用浏览器扩展（如 EditThisCookie）或开发者工具导出 Cookie
3. 将 Cookie 保存为 Netscape 格式文件，命名为 `cookies.txt`，放在项目根目录

Cookie 文件格式示例：
```
# Netscape HTTP Cookie File
.weread.qq.com	TRUE	/	FALSE	1799027743	wr_fp	YOUR_FP_VALUE
.weread.qq.com	TRUE	/	FALSE	1770083765	wr_skey	YOUR_SKEY_VALUE
weread.qq.com	FALSE	/	FALSE	0	wr_gid	YOUR_GID_VALUE
...
```

**注意**：Cookie 可能会过期，如果遇到认证错误，请重新导出 Cookie。

## 使用说明

### 方式一：使用主脚本（推荐）

```bash
python main.py
```

主脚本会按顺序执行：获取书籍列表 → 获取书签 → 获取评论 → 合并笔记

### 方式二：单独运行各个脚本

#### 步骤 1：获取书籍列表

**脚本**：`scripts/fetch_books.py`

**API**：
- `GET /api/user/notebook` - 获取用户笔记本列表
- `GET /web/book/getProgress?bookId={book_id}` - 获取阅读进度

**输出**：`output/fetch_notebooks_output.csv`

**主要字段**：`bookId`, `title`, `author`, `noteCount`, `reviewCount`, `bookmarkCount`, `readingTime` 等

**运行**：
```bash
python scripts/fetch_books.py [cookie_file_path]
```

#### 步骤 2：获取书签（划线）

**脚本**：`scripts/fetch_bookmarks.py`

**API**：`GET /web/book/bookmarklist?bookId={book_id}`

**输出**：`output/bookmarks/{book_id}.csv`

**主要字段**：`bookmarkId`, `chapterName`, `chapterUid`, `markText`, `createTime`

**运行**：
```bash
python scripts/fetch_bookmarks.py [cookie_file_path] [books_csv_file]
```

#### 步骤 3：获取评论（想法）

**脚本**：`scripts/fetch_reviews.py`

**API**：`GET /web/review/list?bookId={book_id}&listType=11&mine=1&synckey=0`

**输出**：`output/reviews/{book_id}.csv`

**主要字段**：`reviewId`, `chapterName`, `chapterUid`, `abstract`, `content`, `createTime`

**运行**：
```bash
python scripts/fetch_reviews.py [cookie_file_path] [books_csv_file]
```

#### 步骤 4：合并笔记

**脚本**：`scripts/merge_notes.py`

**功能**：将书签和评论合并为统一的笔记文件，按章节和创建时间排序，并去重。

**合并逻辑**：

1. 读取书籍列表，依次处理每本书
2. 加载该书的所有书签和评论数据
3. 提取所有 `chapterUid`（章节ID），按升序排序
4. **按章节顺序处理**：
   - 对每个章节，过滤出该章节的所有书签和评论
   - 统一字段：书签的 `markText` 和评论的 `abstract` 统一为 `markText`；评论的 `content` 作为 `reviewContent`
   - 去重：如果 `markText` 相同，优先保留有 `reviewContent` 的记录
   - 章节内按 `createTime` 升序排序
5. 将所有章节的记录按章节顺序合并，生成完整 CSV
6. 如果笔记总数 >= 30 条，保存到 `output/notes/{book_id}.csv`

**输出字段**：`bookId`, `title`, `author`, `categories`, `bookmarkId`, `reviewId`, `chapterName`, `chapterUid`, `markText`, `reviewContent`, `createTime`

**运行**：
```bash
python scripts/merge_notes.py [books_csv_file] [bookmarks_dir] [reviews_dir] [output_dir]
```

## 输出目录结构

```
output/
├── fetch_notebooks_output.csv    # 书籍列表
├── bookmarks/                    # 书签目录
│   └── {book_id}.csv
├── reviews/                      # 评论目录
│   └── {book_id}.csv
└── notes/                        # 合并后的笔记目录
    └── {book_id}.csv
```

## 常见问题

**Cookie 过期**：遇到 `errCode -2012` 或 `401` 错误时，重新导出 Cookie 并更新 `cookies.txt`

**网络请求失败**：检查网络连接，确认微信读书网站可正常访问

**部分书籍没有数据**：某些书籍可能没有书签或评论；合并脚本会跳过笔记数量少于 30 的书籍

## 注意事项

- Cookie 安全：请妥善保管 Cookie 文件，不要分享给他人
- 请求频率：脚本已内置延迟，避免请求过于频繁
- API 变更：微信读书可能会更改 API，如遇问题请检查 API 端点

## 许可证

本项目仅供个人学习和研究使用。
