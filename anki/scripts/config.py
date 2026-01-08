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

