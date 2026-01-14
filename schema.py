#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PostgreSQL Schema Definitions for EReader Notes Exporter
基于项目中所有 CSV 文件类型的 PostgreSQL CREATE TABLE 语句
"""

# ============================================================================
# 1. 书籍列表表 (fetch_notebooks_output.csv)
# PRIMARY KEY is book_id
# NO INDEX is needed 
# ============================================================================
BOOKS_TABLE = """
CREATE TABLE IF NOT EXISTS books (
    "bookId" VARCHAR(50) PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    author VARCHAR(500),
    translator VARCHAR(500),
    "publishTime" TIMESTAMP,
    categories VARCHAR(200),
    "lastChapterIdx" INTEGER,
    "noteCount" INTEGER DEFAULT 0,
    "reviewCount" INTEGER DEFAULT 0,
    "bookmarkCount" INTEGER DEFAULT 0,
    "readingTime" INTEGER,
    "finishTime" TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- books 表的主键是 bookId，不需要额外索引
"""

# ============================================================================
# 2. 书签表 (bookmarks/*.csv)
# bookmark_id is an unique ID includes book_id and chapter_uid
# PRIMARY KEY is bookmark_id
# FOREIGN KEY is book_id
# NO INDEX is needed 
# ============================================================================
BOOKMARKS_TABLE = """
CREATE TABLE IF NOT EXISTS bookmarks (
    "bookmarkId" VARCHAR(100) PRIMARY KEY, 
    "bookId" VARCHAR(50) NOT NULL,
    title VARCHAR(500) NOT NULL,
    author VARCHAR(500),
    categories VARCHAR(200),
    "markText" TEXT,
    "chapterName" VARCHAR(500),
    "chapterUid" INTEGER,
    "colorStyle" INTEGER,
    style VARCHAR(50),
    "createTime" BIGINT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY ("bookId") REFERENCES books("bookId") ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_bookmarks_book_id ON bookmarks("bookId");
"""

# ============================================================================
# 3. 点评表 (reviews/*.csv)
# review_id is an unique ID which not includes book_id and chapter_uid
# PRIMARY KEY is review_id
# FOREIGN KEY is book_id
# NO INDEX is needed 
# ============================================================================
REVIEWS_TABLE = """
CREATE TABLE IF NOT EXISTS reviews (
    "reviewId" VARCHAR(100) PRIMARY KEY,
    "bookId" VARCHAR(50) NOT NULL,
    title VARCHAR(500) NOT NULL,
    author VARCHAR(500),
    categories VARCHAR(200),
    content TEXT,
    "chapterName" VARCHAR(500),
    "chapterUid" INTEGER,
    "createTime" BIGINT,
    abstract TEXT,
    range VARCHAR(200),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY ("bookId") REFERENCES books("bookId") ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_reviews_book_id ON reviews("bookId");
"""

# ============================================================================
# 4. 合并笔记表 (notes/*.csv)
# ============================================================================
NOTES_TABLE = """
CREATE TABLE IF NOT EXISTS notes (
    "noteId" VARCHAR(200) PRIMARY KEY,
    "bookId" VARCHAR(50) NOT NULL,
    title VARCHAR(500) NOT NULL,
    author VARCHAR(500),
    categories VARCHAR(200),
    "bookmarkId" VARCHAR(100),
    "reviewId" VARCHAR(100),
    "chapterName" VARCHAR(500),
    "chapterUid" INTEGER,
    "markText" TEXT,
    "reviewContent" TEXT,
    "createTime" BIGINT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY ("bookId") REFERENCES books("bookId") ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_notes_book_id ON notes("bookId");
"""

# ============================================================================
# 5. 概念表 (concepts/*.csv)
# ============================================================================
CONCEPTS_TABLE = """
CREATE TABLE IF NOT EXISTS concepts (
    "conceptId" VARCHAR(500) PRIMARY KEY,
    "bookId" VARCHAR(50) NOT NULL,
    concept VARCHAR(500) NOT NULL,
    domain VARCHAR(200),
    category VARCHAR(200),
    source VARCHAR(500),
    "chapterRange" VARCHAR(50),
    sentences TEXT,
    short_definition VARCHAR(500),
    definition TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY ("bookId") REFERENCES books("bookId") ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_concepts_book_id ON concepts("bookId");
"""

# ============================================================================
# 6. Guidebook 表 (guidebook/*.csv)
# ============================================================================
GUIDEBOOK_TABLE = """
CREATE TABLE IF NOT EXISTS guidebook (
    "CardName" VARCHAR(500) PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    categories VARCHAR(200),
    "chapterName" VARCHAR(500),
    "chapterUid" INTEGER,
    "markText" TEXT,
    "markTextIndex" INTEGER,
    "bookmarkId" VARCHAR(100),
    explanation TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- guidebook 表没有 bookId 字段，不需要索引
"""

# ============================================================================
# 所有表的创建语句（按依赖顺序）
# ============================================================================
ALL_TABLES = [
    BOOKS_TABLE,
    BOOKMARKS_TABLE,
    REVIEWS_TABLE,
    NOTES_TABLE,
    CONCEPTS_TABLE,
    GUIDEBOOK_TABLE,
]

# ============================================================================
# 生成完整的 SQL 脚本
# ============================================================================
def get_all_sql() -> str:
    """
    获取所有表的 CREATE TABLE 语句
    
    Returns:
        完整的 SQL 脚本字符串
    """
    return "\n".join(ALL_TABLES)


def get_table_sql(table_name: str) -> str:
    """
    根据表名获取对应的 CREATE TABLE 语句
    
    Args:
        table_name: 表名（books, bookmarks, reviews, notes, concepts, guidebook）
    
    Returns:
        CREATE TABLE 语句字符串
    """
    table_map = {
        'books': BOOKS_TABLE,
        'bookmarks': BOOKMARKS_TABLE,
        'reviews': REVIEWS_TABLE,
        'notes': NOTES_TABLE,
        'concepts': CONCEPTS_TABLE,
        'guidebook': GUIDEBOOK_TABLE,
    }
    
    if table_name.lower() not in table_map:
        raise ValueError(f"Unknown table name: {table_name}. Available: {list(table_map.keys())}")
    
    return table_map[table_name.lower()]


# ============================================================================
# 表结构说明
# ============================================================================
TABLE_DESCRIPTIONS = {
    'books': {
        'description': '书籍列表表，存储从微信读书获取的书籍基本信息',
        'source': 'wereader/output/fetch_notebooks_output.csv',
        'primary_key': 'bookId',
        'foreign_keys': [],
    },
    'bookmarks': {
        'description': '书签表，存储书籍中的划线笔记（书签）',
        'source': 'wereader/output/bookmarks/*.csv',
        'primary_key': 'bookmarkId',
        'foreign_keys': ['bookId -> books(bookId)'],
    },
    'reviews': {
        'description': '点评表，存储书籍中的点评笔记',
        'source': 'wereader/output/reviews/*.csv',
        'primary_key': 'reviewId',
        'foreign_keys': ['bookId -> books(bookId)'],
    },
    'notes': {
        'description': '合并笔记表，合并了书签和点评的笔记数据',
        'source': 'wereader/output/notes/*.csv',
        'primary_key': 'noteId',
        'foreign_keys': [
            'bookId -> books(bookId)',
        ],
    },
    'concepts': {
        'description': '概念表，存储从笔记中提取的概念词及其定义',
        'source': 'llm/output/concepts/*.csv',
        'primary_key': 'conceptId',
        'foreign_keys': [
            'bookId -> books(bookId)',
        ],
    },
    'guidebook': {
        'description': 'Guidebook 表，存储 LLM 生成的逐句解释（学习指南）',
        'source': 'llm/output/guidebook/*.csv',
        'primary_key': 'CardName',
        'foreign_keys': [],
    },
}


if __name__ == "__main__":
    """
    直接运行此脚本可以打印所有表的创建语句
    """
    print("=" * 80)
    print("PostgreSQL Schema Definitions for EReader Notes Exporter")
    print("=" * 80)
    print()
    
    print("表结构说明：")
    print("-" * 80)
    for table_name, info in TABLE_DESCRIPTIONS.items():
        print(f"\n表名: {table_name}")
        print(f"  描述: {info['description']}")
        print(f"  数据源: {info['source']}")
        print(f"  主键: {info['primary_key']}")
        if info['foreign_keys']:
            print(f"  外键:")
            for fk in info['foreign_keys']:
                print(f"    - {fk}")
    
    print("\n" + "=" * 80)
    print("完整的 SQL 创建语句：")
    print("=" * 80)
    print()
    print(get_all_sql())

