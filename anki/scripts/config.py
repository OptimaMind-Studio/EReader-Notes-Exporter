"""
Anki 导入配置
定义 AnkiConnect API 配置、卡牌组命名格式、卡牌模板等配置项
用户可以修改这些配置
"""

# AnkiConnect API 配置
ANKI_CONNECT_URL = "http://127.0.0.1:8765"
ANKI_CONNECT_PORT = 8765
ANKI_CONNECT_HOST = "127.0.0.1"

# 卡牌模板名称
ANKI_MODEL_NAME = "KWDict"

# 卡牌组命名格式
# 格式：{prefix}::{category}::{book_title}
# 例如：微信读书::guidebook::极简央行课
DECK_NAME_PREFIX = "微信读书"
DECK_NAME_CATEGORY = "guidebook"
DECK_NAME_FORMAT = f"{DECK_NAME_PREFIX}::{DECK_NAME_CATEGORY}::{{book_title}}"

# 默认标签
DEFAULT_TAGS = ["guidebook", "微信读书"]

# CSV 列名 -> Anki 字段名 的映射
FIELD_MAPPING = {
    'CardName': 'Name',
    'title': 'Source',
    'categories': 'Field',
    'chapterName': 'Taxonomy',
    'explanation': 'AINotes',
    'markText': 'References'
}

# Concepts 卡牌组命名格式
# 格式：{prefix}::{category}::{book_title}
# 例如：微信读书::concepts::极简央行课
CONCEPTS_DECK_NAME_CATEGORY = "concepts"
CONCEPTS_DECK_NAME_FORMAT = f"{DECK_NAME_PREFIX}::{CONCEPTS_DECK_NAME_CATEGORY}::{{book_title}}"

# Concepts CSV 列名 -> Anki 字段名 的映射
CONCEPTS_FIELD_MAPPING = {
    'concept': 'Name',           # 概念名称 -> Name
    'source': 'Source',          # 来源（书名） -> Source
    'domain': 'Field',           # 领域 -> Field
    'category': 'Taxonomy',      # 分类 -> Taxonomy
    'definition': 'AINotes',     # 定义（HTML） -> AINotes
    'chapterRange': 'References'  # 章节范围（章节号-章节名） -> References
}
# Outline 卡牌组命名格式
# 格式：{prefix}::{category}::{book_title}
# 例如：微信读书::outline::极简央行课
OUTLINE_DECK_NAME_CATEGORY = "outline"
OUTLINE_DECK_NAME_FORMAT = f"{DECK_NAME_PREFIX}::{OUTLINE_DECK_NAME_CATEGORY}::{{book_title}}"

# Outline 字段映射（从 HTML 表格解析出的数据 -> Anki 字段名）
OUTLINE_FIELD_MAPPING = {
    'concept': 'Name',           # 概念词 -> Name
    'source': 'Source',          # 来源（书名） -> Source
    'domain': 'Field',           # 领域 -> Field
    'category': 'Taxonomy',      # 范畴 -> Taxonomy
    'explanation': 'AINotes',    # 解释 -> AINotes
    'block_number': 'References'  # 层级概念块编号 -> References
}
