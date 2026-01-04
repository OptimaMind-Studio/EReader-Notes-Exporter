# 合并笔记逻辑说明

`merge_notes.py` 的作用是混合 `output/bookmarks` 和 `output/reviews` 目录中的内容，生成统一的笔记文件。

## 处理流程

### 1. 读取书籍列表

- 从 `output/fetch_notebooks_output.csv` 文件中读取所有 `bookId`
- 依次处理每本书

### 2. 加载书签和评论数据

- 从 `output/bookmarks/` 目录中找到对应 `bookId` 的 CSV 文件，读取书签数据，得到书签表（bookmarks table）
- 从 `output/reviews/` 目录中找到对应 `bookId` 的 CSV 文件，读取评论数据，得到评论表（reviews table）
- **注意**：评论文件可能不存在（如果该书没有评论）

### 3. 提取章节列表

- 从书签表和评论表中提取所有的 `chapterUid`
- 将所有 `chapterUid` 合并去重，按**升序排序**
- 依次处理每个 `chapterUid`

### 4. 按章节处理数据

对每个 `chapterUid` 执行以下步骤：

#### 4.1 过滤数据

- 过滤出当前 `chapterUid` 对应的所有书签记录
- 过滤出当前 `chapterUid` 对应的所有评论记录

#### 4.2 统一字段格式

- **markText 字段**：
  - 书签记录：使用书签表中的 `markText` 字段
  - 评论记录：使用评论表中的 `abstract` 字段（评论的 `abstract` 等效为书签的 `markText`）
  - 将两类记录的 `markText`/`abstract` 统一为 `markText` 字段

- **reviewContent 字段**：
  - 如果记录来自书签：`reviewContent` 为空字符串
  - 如果记录来自评论：`reviewContent` 使用评论表中的 `content` 字段

#### 4.3 去重处理

- 所有记录都带有各自的 `createTime`（创建时间）
- 按照 `markText` 字段进行去重
- 如果存在多条记录的 `markText` 相同：
  - 保留 `reviewContent` 不为空的那条记录（优先保留有评论内容的记录）
  - 如果多条记录的 `reviewContent` 都为空或都不为空，保留第一条

#### 4.4 章节内排序

- 在当前 `chapterUid` 组内，按照 `createTime` 升序排序

#### 4.5 生成统一格式的记录

每条记录包含以下字段：
- `bookId` - 书籍ID
- `title` - 书名
- `author` - 作者
- `categories` - 分类
- `bookmarkId` - 书签ID（如果记录来自书签，否则为空）
- `reviewId` - 评论ID（如果记录来自评论，否则为空）
- `chapterName` - 章节名称
- `chapterUid` - 章节UID
- `markText` - 统一的划线文本字段
- `reviewContent` - 评论内容（仅评论记录有内容）
- `createTime` - 创建时间（时间戳）

### 5. 合并所有章节

- 依次处理完所有的 `chapterUid` 后
- 将所有章节的记录按章节顺序合并，生成完整的 CSV 文件
- 最终输出：先按章节顺序（chapterUid 升序），再按时间顺序（createTime 升序）

### 6. 过滤和保存

- 统计合并后的 CSV 文件总行数
- 如果总行数少于 30 条，跳过该书籍，不生成文件
- 如果总行数 >= 30 条，保存到 `output/notes/` 目录
- 文件名格式：`{bookId}.csv`（以书籍为单位存储）

## 总结

- ✅ 合并是**按章节（chapterUid）为单位**进行的
- ✅ 每个章节内的书签和评论会合并在一起
- ✅ 不同章节的记录会按章节顺序（chapterUid 升序）排列
- ✅ 每个章节内的记录会按创建时间（createTime 升序）排序
- ✅ 最终输出：先按章节顺序，再按时间顺序
