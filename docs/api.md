# 微信读书 API 文档

本文档整理了项目中使用的所有微信读书相关 API 的调用方式和功能说明。

## 基础信息

- **Base URL**: `https://weread.qq.com`
- **认证方式**: Cookie 认证（需要包含有效的登录 Cookie）

## 通用请求头

所有 API 请求都需要包含以下请求头：

| Header | 值 | 说明 |
|--------|-----|------|
| User-Agent | Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/73.0.3683.103 Safari/537.36 | 浏览器标识 |
| Accept-Encoding | gzip, deflate, br | 支持的编码格式 |
| Accept-Language | zh-CN,zh;q=0.9,en;q=0.8 | 语言偏好 |
| Accept | application/json, text/plain, */* | 接受的内容类型 |
| Content-Type | application/json | 请求内容类型（POST 请求） |
| Cookie | [登录 Cookie 字符串] | 认证信息 |

## API 列表

### 1. 获取用户笔记本列表

**功能**: 获取当前登录用户的所有笔记本（书籍）列表

**Endpoint**: 
```
GET /api/user/notebook
```

**请求参数**: 无

**响应说明**:
- 返回用户的所有书籍列表，包含书籍的基本信息（bookId、标题、作者等）
- 如果返回 401 状态码且 errcode 为 -2012，表示登录超时，需要刷新 Cookie

**错误处理**:
- 401 状态码: 登录超时或未登录，需要重新登录
- errcode -2012: 登录超时，会自动尝试刷新 Cookie

---

### 2. 获取书籍详情

**功能**: 获取指定书籍的详细信息，包括标题、作者、封面、价格、简介等

**Endpoint**:
```
GET /web/book/info?bookId={bookId}
```

**请求参数**:
| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| bookId | string | 是 | 书籍ID |

**响应说明**:
- 返回书籍的详细信息，包括：

**重要字段说明**：

| 字段名 | 类型 | 说明 |
|--------|------|------|
| **基本信息** | | |
| bookId | string | 书籍唯一标识ID |
| title | string | 书名 |
| author | string | 作者 |
| translator | string | 译者 |
| **出版信息** | | |
| publishTime | string | 出版时间 |
| **分类信息** | | |
| categories | array | 分类详情数组，包含categoryId、subCategoryId、title等 |
| **阅读信息** | | |
| lastChapterIdx | number | 最后章节索引 |
| **用户统计** | | |
| noteCount | number | 笔记数量（来自笔记本列表） |
| reviewCount | number | 评论数量（来自笔记本列表） |
| bookmarkCount | number | 划线数量（来自笔记本列表） |

**错误处理**:
- errCode -2012: 登录超时，会自动尝试刷新 Cookie

---

### 3. 获取书籍划线

**功能**: 获取指定书籍的所有划线（标注）信息

**Endpoint**:
```
GET /web/book/bookmarklist?bookId={bookId}
```

**请求参数**:
| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| bookId | string | 是 | 书籍ID |

**响应说明**:
- 返回书籍的所有划线信息，包括：
  - synckey: 同步键
  - updated: 更新的划线列表，包含：
    - bookmarkId: 划线ID
    - markText: 划线文本
    - chapterName: 章节名称
    - chapterUid: 章节ID
    - createTime: 创建时间
    - colorStyle: 颜色样式
    - style: 样式类型
    - range: 范围信息
  - removed: 已删除的划线列表
  - chapters: 章节信息
  - book: 书籍基本信息

---

### 4. 获取书籍评论/想法

**功能**: 获取指定书籍的用户评论和想法

**Endpoint**:
```
GET /web/review/list?bookId={bookId}&listType=11&mine=1&synckey=0
```

**请求参数**:
| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| bookId | string | 是 | 书籍ID |
| listType | number | 是 | 列表类型，固定为 11 |
| mine | number | 是 | 是否只获取自己的评论，1 表示是 |
| synckey | number | 是 | 同步键，0 表示从头开始 |

**响应说明**:
- 返回书籍的评论列表，包括：
  - synckey: 同步键
  - totalCount: 总评论数
  - reviews: 评论列表，包含：
    - reviewId: 评论ID
    - content: 评论内容
    - htmlContent: HTML 格式的评论内容
    - chapterName: 章节名称
    - chapterUid: 章节ID
    - createTime: 创建时间
    - abstract: 摘要
    - range: 范围信息
    - book: 书籍信息
    - author: 作者信息
  - hasMore: 是否还有更多评论

---

### 5. 获取书籍章节信息

**功能**: 获取指定书籍的章节列表和结构信息

**Endpoint**:
```
POST /web/book/chapterInfos
```

**请求参数**:
请求体为 JSON 格式：
```json
{
  "bookIds": ["bookId"]
}
```

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| bookIds | string[] | 是 | 书籍ID数组 |

**响应说明**:
- 返回章节信息，包括：
  - data: 数据数组，每个元素包含：
    - bookId: 书籍ID
    - chapterUpdateTime: 章节更新时间
    - updated: 章节列表，包含：
      - chapterUid: 章节ID
      - chapterIdx: 章节索引
      - title: 章节标题
      - updateTime: 更新时间
      - level: 章节层级
      - isMPChapter: 是否为公众号章节

---

### 6. 获取书籍阅读进度

**功能**: 获取指定书籍的阅读进度信息，包括阅读时间、进度百分比等

**Endpoint**:
```
GET /web/book/getProgress?bookId={bookId}
```

**请求参数**:
| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| bookId | string | 是 | 书籍ID |

**响应说明**:
- 返回阅读进度信息，包括：
  - bookId: 书籍ID
  - book: 书籍进度详情，包含：
    - chapterUid: 当前章节ID
    - chapterIdx: 当前章节索引
    - chapterOffset: 章节偏移量
    - progress: 阅读进度（百分比）
    - readingTime: 阅读时间（秒）
    - startReadingTime: 开始阅读时间
    - finishTime: 完成时间
    - isStartReading: 是否开始阅读
  - canFreeRead: 是否可以免费阅读
  - timestamp: 时间戳

---

## 错误码说明

| 错误码 | 说明 | 处理方式 |
|--------|------|----------|
| -2012 | 登录超时 | 自动尝试刷新 Cookie，如果失败则提示重新登录 |
| 401 | 未授权 | 需要重新登录 |

## 注意事项

1. **Cookie 管理**: 所有 API 都需要有效的 Cookie 进行认证，Cookie 过期后需要重新登录
2. **自动刷新**: 当检测到 Cookie 过期（errcode -2012）时，系统会自动尝试刷新 Cookie
3. **重试机制**: 获取笔记本列表时，如果第一次失败会自动重试一次
4. **废弃 API**: `getBookReadInfo` 方法已废弃，建议使用 `getProgress` 方法代替

## 数据模型

详细的响应数据模型定义请参考 `src/models.ts` 文件，包括：
- `HighlightResponse`: 划线响应
- `BookReviewResponse`: 评论响应
- `ChapterResponse`: 章节响应
- `BookDetailResponse`: 书籍详情响应
- `BookProgressResponse`: 阅读进度响应
- `BookReadInfoResponse`: 阅读信息响应（已废弃）

