#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
将 marknotes CSV 文件导入到 Anki
使用 AnkiConnect API 将 MarkNotes 卡片添加到 Anki
"""

import json
import csv
import os
import sys
import requests
import argparse
from pathlib import Path
from typing import Dict, List, Optional
from config import (
    ANKI_CONNECT_URL,
    ANKI_MODEL_NAME,
    DECK_NAME_PREFIX,
    DEFAULT_TAGS
)

# 导入 generate_marknotes 模块
try:
    # 从项目根目录运行时
    script_dir = Path(__file__).parent  # anki/scripts
    project_root = script_dir.parent.parent  # 项目根目录
    sys.path.insert(0, str(project_root))
    from llm.scripts.generate_marknotes import process_csv_file as generate_marknotes
except ImportError:
    # 如果导入失败，尝试直接导入
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent.parent / "llm" / "scripts"))
        from generate_marknotes import process_csv_file as generate_marknotes
    except ImportError:
        generate_marknotes = None

# MarkNotes 卡牌组命名格式
# 格式：{prefix}::{category}::{book_title}
# 例如：微信读书::marknotes::极简央行课
MARKNOTES_DECK_NAME_CATEGORY = "marknotes"
MARKNOTES_DECK_NAME_FORMAT = f"{DECK_NAME_PREFIX}::{MARKNOTES_DECK_NAME_CATEGORY}::{{book_title}}"

# MarkNotes CSV 列名 -> Anki 字段名 的映射
MARKNOTES_FIELD_MAPPING = {
    'reviewContentHTML': 'AINotes',  # HTML 内容 -> AINotes
    'title': 'Source',                # 书名 -> Source
    'categories': 'Field',            # 分类 -> Field
    'markText': 'References'          # 原文 -> References
    # Name 字段需要特殊处理：书名-chapterName-reviewId
}


class AnkiConnectClient:
    """AnkiConnect API 客户端"""
    
    def __init__(self, url: Optional[str] = None):
        """
        初始化 AnkiConnect 客户端
        
        Args:
            url: AnkiConnect API 地址（如果为 None，使用配置文件中的默认值）
        """
        self.url = url or ANKI_CONNECT_URL
    
    def _invoke(self, action: str, **params) -> Dict:
        """
        调用 AnkiConnect API
        
        Args:
            action: API 动作名称
            **params: API 参数
        
        Returns:
            API 响应结果
        """
        payload = {
            "action": action,
            "version": 6,
            "params": params
        }
        
        try:
            response = requests.post(self.url, json=payload, timeout=10)
            response.raise_for_status()
            result = response.json()
            
            if len(result) != 2:
                raise Exception(f"响应格式错误: {result}")
            
            if result.get("error") is not None:
                raise Exception(f"AnkiConnect 错误: {result['error']}")
            
            return result.get("result")
        
        except requests.exceptions.ConnectionError:
            raise Exception("无法连接到 AnkiConnect。请确保 Anki 正在运行，并且已安装 AnkiConnect 插件。")
        except requests.exceptions.Timeout:
            raise Exception("AnkiConnect 请求超时")
        except Exception as e:
            raise Exception(f"调用 AnkiConnect API 失败: {e}")
    
    def get_model_field_names(self, model_name: str) -> List[str]:
        """
        获取卡牌模板的字段名列表
        
        Args:
            model_name: 卡牌模板名称
        
        Returns:
            字段名列表
        """
        return self._invoke("modelFieldNames", modelName=model_name)
    
    def deck_exists(self, deck_name: str) -> bool:
        """
        检查卡牌组是否存在
        
        Args:
            deck_name: 卡牌组名称
        
        Returns:
            如果存在返回 True，否则返回 False
        """
        deck_names = self._invoke("deckNames")
        return deck_name in deck_names
    
    def ensure_deck_exists(self, deck_name: str) -> bool:
        """
        确保卡牌组存在，如果不存在则创建
        
        Args:
            deck_name: 卡牌组名称
        
        Returns:
            如果成功返回 True，否则返回 False
        """
        try:
            self._invoke("createDeck", deck=deck_name)
            return True
        except Exception as e:
            error_msg = str(e).lower()
            if "already exists" in error_msg or "已存在" in error_msg:
                return True
            return False
    
    def find_duplicate_notes(self, deck_name: str, model_name: str, fields: Dict[str, str]) -> List[int]:
        """
        查找重复的卡片（基于 Name 字段）
        
        Args:
            deck_name: 卡牌组名称
            model_name: 卡牌模板名称
            fields: 卡片字段字典
        
        Returns:
            重复卡片的 note ID 列表
        """
        if 'Name' not in fields:
            return []
        
        # 使用 Name 字段进行精确匹配
        name_value = fields['Name']
        if not name_value or not name_value.strip():
            return []
        
        # 转义特殊字符
        escaped_name = name_value.replace('"', '\\"')
        query = f'deck:"{deck_name}" note:"{model_name}" "Name:{escaped_name}"'
        
        try:
            note_ids = self._invoke("findNotes", query=query)
            return note_ids if note_ids else []
        except Exception as e:
            # 如果查询失败，返回空列表
            return []
    
    def add_note(self, deck_name: str, model_name: str, fields: Dict[str, str], tags: List[str] = None) -> Optional[int]:
        """
        添加一张卡片
        
        Args:
            deck_name: 卡牌组名称
            model_name: 卡牌模板名称
            fields: 卡片字段字典
            tags: 标签列表
        
        Returns:
            新创建的卡片 ID，如果失败返回 None
        """
        note = {
            "deckName": deck_name,
            "modelName": model_name,
            "fields": fields,
            "tags": tags or []
        }
        
        try:
            note_id = self._invoke("addNote", note=note)
            return note_id
        except Exception as e:
            error_msg = str(e).lower()
            if "duplicate" in error_msg or "重复" in error_msg:
                # 如果是重复卡片，返回 None
                return None
            raise
    
    def add_notes(self, notes: List[Dict]) -> List[Optional[int]]:
        """
        批量添加卡片
        
        Args:
            notes: 卡片列表，每个卡片是一个字典，包含 deckName, modelName, fields, tags
        
        Returns:
            新创建的卡片 ID 列表，如果失败则对应位置为 None
        """
        try:
            note_ids = self._invoke("addNotes", notes=notes)
            return note_ids
        except Exception as e:
            raise Exception(f"批量添加卡片失败: {e}")
    
    def update_note_fields(self, note_id: int, fields: Dict[str, str]) -> bool:
        """
        更新卡片的字段
        
        Args:
            note_id: 卡片 ID
            fields: 要更新的字段字典
        
        Returns:
            如果成功返回 True，否则返回 False
        """
        try:
            self._invoke("updateNoteFields", note={"id": note_id, "fields": fields})
            return True
        except Exception as e:
            return False
    
    def sync(self) -> bool:
        """
        同步 Anki 到 AnkiWeb
        
        Returns:
            如果成功返回 True，否则返回 False
        """
        try:
            # AnkiConnect 的 sync API 会触发同步，成功时通常返回 None
            # 注意：sync 是异步操作，可能需要一些时间
            result = self._invoke("sync")
            # sync 操作成功时通常返回 None 或空值
            # 即使返回 None 也认为是成功（因为 sync 是异步的）
            return True
        except Exception as e:
            error_msg = str(e).lower()
            # 检查是否是常见的同步错误
            if "authentication" in error_msg.lower() or "login" in error_msg.lower() or "not logged in" in error_msg.lower():
                print(f"  ⚠️  同步失败: 请先在 Anki 中登录 AnkiWeb 账号")
                print(f"     操作步骤：Anki -> 文件 -> 同步 -> 登录 AnkiWeb")
            elif "already syncing" in error_msg.lower() or "sync in progress" in error_msg.lower():
                print(f"  ⚠️  同步失败: Anki 正在同步中，请稍后再试")
            elif "network" in error_msg.lower() or "connection" in error_msg.lower():
                print(f"  ⚠️  同步失败: 网络连接问题，请检查网络连接")
            else:
                print(f"  ⚠️  同步失败: {error_msg}")
                print(f"     提示：请确保已在 Anki 中登录 AnkiWeb 账号，并且网络连接正常")
            return False


def read_csv_file(csv_file: Path) -> List[Dict[str, str]]:
    """读取 CSV 文件"""
    rows = []
    if not csv_file.exists():
        print(f"⚠️  文件不存在: {csv_file}")
        return rows
    
    try:
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
    except Exception as e:
        print(f"读取文件时出错: {e}")
    
    return rows


def get_book_title_from_csv(csv_file: Path) -> Optional[str]:
    """
    从 CSV 文件中获取书名（从第一行）
    
    Args:
        csv_file: CSV 文件路径
    
    Returns:
        书名，如果未找到则返回 None
    """
    rows = read_csv_file(csv_file)
    if rows:
        return rows[0].get('title', '').strip()
    return None


def map_csv_fields_to_anki_fields(csv_row: Dict[str, str], field_mapping: Dict[str, str]) -> Dict[str, str]:
    """
    将 CSV 行数据映射到 Anki 字段
    
    Args:
        csv_row: CSV 行数据字典
        field_mapping: 字段映射关系
    
    Returns:
        Anki 字段字典
    """
    anki_fields = {}
    
    # 特殊处理 Name 字段：书名-chapterName-reviewId
    book_title = csv_row.get('title', '').strip()
    chapter_name = csv_row.get('chapterName', '').strip()
    review_id = csv_row.get('reviewId', '').strip()
    
    # 构建 Name 字段
    name_parts = []
    if book_title:
        name_parts.append(book_title)
    if chapter_name:
        name_parts.append(chapter_name)
    if review_id:
        name_parts.append(review_id)
    
    anki_fields['Name'] = '-'.join(name_parts) if name_parts else ''
    
    # 映射其他字段
    for csv_field, anki_field in field_mapping.items():
        value = csv_row.get(csv_field, '').strip()
        anki_fields[anki_field] = value
    
    return anki_fields


def import_csv_to_anki(csv_file: Path, anki_client: AnkiConnectClient, model_name: Optional[str] = None, 
                       field_mapping: Optional[Dict[str, str]] = None, dry_run: bool = False, sync: bool = False,
                       batch_size: int = 100):
    """
    将 CSV 文件导入到 Anki
    
    Args:
        csv_file: CSV 文件路径
        anki_client: AnkiConnect 客户端
        model_name: Anki 卡牌模板名称（默认: KWDict）
        field_mapping: 字段映射关系（如果为 None，使用默认映射）
        dry_run: 是否为试运行（不实际添加卡片）
        sync: 是否同步到 AnkiWeb（已弃用，现在总是会自动同步）
        batch_size: 批量添加卡片的批次大小
    """
    if field_mapping is None:
        field_mapping = MARKNOTES_FIELD_MAPPING
    
    if model_name is None:
        model_name = ANKI_MODEL_NAME
    
    print(f"\n{'='*60}")
    print(f"处理文件: {csv_file.name}")
    print(f"{'='*60}")
    
    # 读取 CSV 文件
    rows = read_csv_file(csv_file)
    if not rows:
        print(f"⚠️  文件为空或读取失败，跳过")
        return
    
    print(f"读取到 {len(rows)} 条记录")
    
    # 获取书名（从第一行）
    book_title = get_book_title_from_csv(csv_file)
    if not book_title:
        print(f"⚠️  无法获取书名，跳过")
        return
    
    # 构建卡牌组名称（使用配置中的格式）
    deck_name = MARKNOTES_DECK_NAME_FORMAT.format(book_title=book_title)
    print(f"卡牌组: {deck_name}")
    print(f"卡牌模板: {model_name}")
    
    # 确保卡牌组存在，如果不存在则创建
    if not anki_client.deck_exists(deck_name):
        print(f"卡牌组不存在，正在创建...")
        if anki_client.ensure_deck_exists(deck_name):
            print(f"✓ 成功创建卡牌组: {deck_name}")
        else:
            print(f"❌ 错误：无法创建卡牌组: {deck_name}")
            return
    else:
        print(f"✓ 卡牌组已存在: {deck_name}")
    
    # 验证卡牌模板是否存在
    try:
        field_names = anki_client.get_model_field_names(model_name)
        print(f"卡牌模板字段: {', '.join(field_names)}")
    except Exception as e:
        print(f"❌ 错误：无法获取卡牌模板 '{model_name}' 的信息: {e}")
        return
    
    # 验证映射的字段是否存在于卡牌模板中
    mapped_fields = set(field_mapping.values())
    mapped_fields.add('Name')  # Name 字段是特殊处理的
    missing_fields = mapped_fields - set(field_names)
    if missing_fields:
        print(f"⚠️  警告：以下映射的字段在卡牌模板中不存在: {', '.join(missing_fields)}")
    
    # 准备要添加的卡片
    notes_to_add = []
    skipped_count = 0
    duplicate_count = 0
    
    print(f"\n检查重复卡片...")
    for i, row in enumerate(rows, 1):
        # 映射字段
        anki_fields = map_csv_fields_to_anki_fields(row, field_mapping)
        
        # 检查必填字段（Name 字段和 AINotes 字段）
        if not anki_fields.get('Name', '').strip():
            skipped_count += 1
            continue
        
        if not anki_fields.get('AINotes', '').strip():
            skipped_count += 1
            continue
        
        # 检查是否已存在重复卡片（基于 Name 字段）
        duplicate_notes = anki_client.find_duplicate_notes(deck_name, model_name, anki_fields)
        if duplicate_notes:
            duplicate_count += 1
            continue
        
        # 构建卡片数据
        note = {
            "deckName": deck_name,
            "modelName": model_name,
            "fields": anki_fields,
            "tags": DEFAULT_TAGS + ["marknotes"]
        }
        
        notes_to_add.append(note)
    
    if skipped_count > 0:
        print(f"跳过 {skipped_count} 条记录（缺少必填字段）")
    if duplicate_count > 0:
        print(f"跳过 {duplicate_count} 条记录（已存在的重复卡片）")
    
    if not notes_to_add:
        print("没有有效的记录需要添加")
        return
    
    print(f"\n准备添加 {len(notes_to_add)} 张卡片...")
    
    if dry_run:
        print("🔍 试运行模式：不会实际添加卡片")
        for i, note in enumerate(notes_to_add[:3], 1):  # 只显示前3张
            print(f"\n卡片 {i}:")
            print(json.dumps({
                "deckName": note['deckName'],
                "modelName": note['modelName'],
                "fields": {k: v[:100] + '...' if len(v) > 100 else v for k, v in note['fields'].items()},
                "tags": note['tags']
            }, ensure_ascii=False, indent=2))
        if len(notes_to_add) > 3:
            print(f"\n... 还有 {len(notes_to_add) - 3} 张卡片")
        return
    
    # 批量添加卡片
    added_count = 0
    failed_count = 0
    duplicate_count_final = 0
    
    for i in range(0, len(notes_to_add), batch_size):
        batch = notes_to_add[i:i + batch_size]
        batch_num = i // batch_size + 1
        
        try:
            note_ids = anki_client.add_notes(batch)
            # 统计成功添加的数量（非 None 的 ID）
            success_in_batch = sum(1 for note_id in note_ids if note_id is not None)
            added_count += success_in_batch
            failed_in_batch = len(batch) - success_in_batch
            if failed_in_batch > 0:
                print(f"  批次 {batch_num}: 批量添加部分失败，改为逐个添加...")
                # 逐个添加失败的卡片
                for note in batch:
                    try:
                        note_id = anki_client.add_note(
                            deck_name=note['deckName'],
                            model_name=note['modelName'],
                            fields=note['fields'],
                            tags=note.get('tags', [])
                        )
                        if note_id:
                            added_count += 1
                        else:
                            failed_count += 1
                    except Exception as e:
                        error_msg = str(e)
                        if 'duplicate' in error_msg.lower():
                            duplicate_count_final += 1
                        else:
                            failed_count += 1
        except Exception as e:
            error_msg = str(e)
            print(f"  批次 {batch_num}: 批量添加失败，改为逐个添加...")
            # 批量失败，改为逐个添加
            for note in batch:
                try:
                    note_id = anki_client.add_note(
                        deck_name=note['deckName'],
                        model_name=note['modelName'],
                        fields=note['fields'],
                        tags=note.get('tags', [])
                    )
                    if note_id:
                        added_count += 1
                    else:
                        failed_count += 1
                except Exception as e2:
                    error_msg2 = str(e2)
                    if 'duplicate' in error_msg2.lower():
                        duplicate_count_final += 1
                    else:
                        failed_count += 1
    
    print(f"\n✓ 完成！共添加 {added_count}/{len(notes_to_add)} 张卡片到 Anki")
    if duplicate_count_final > 0:
        print(f"⚠️  跳过 {duplicate_count_final} 张卡片（可能是重复卡片）")
    if failed_count > 0:
        print(f"❌ 失败 {failed_count} 张卡片")


def find_book_id_by_title(csv_file: Path, book_title: str) -> Optional[str]:
    """
    根据书名在 CSV 文件中查找 bookId
    支持精确匹配和部分匹配
    
    Args:
        csv_file: CSV 文件路径
        book_title: 书名
    
    Returns:
        bookId，如果未找到则返回 None
    """
    try:
        book_title_lower = book_title.strip().lower()
        exact_match = None
        partial_matches = []
        
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                title = row.get('title', '').strip()
                title_lower = title.lower()
                book_id = row.get('bookId', '').strip()
                
                # 精确匹配
                if title == book_title or title_lower == book_title_lower:
                    exact_match = book_id
                    break
                
                # 部分匹配：输入的书名包含在 CSV 的 title 中，或 CSV 的 title 包含在输入的书名中
                if book_title_lower in title_lower or title_lower in book_title_lower:
                    partial_matches.append((title, book_id))
        
        # 优先返回精确匹配
        if exact_match:
            return exact_match
        
        # 如果有部分匹配，返回第一个（通常是最相关的）
        if partial_matches:
            # 优先返回包含输入书名最短的那个（更精确）
            partial_matches.sort(key=lambda x: len(x[0]))
            return partial_matches[0][1]
        
        return None
    except Exception as e:
        print(f"错误：读取 CSV 文件失败: {e}")
        return None


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='将 marknotes CSV 文件导入到 Anki',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  # 导入所有 marknotes 文件
  python import_marknotes_to_anki.py
  
  # 导入指定的 CSV 文件
  python import_marknotes_to_anki.py --file llm/output/marknotes/3300089819_marknotes.csv
  
  # 根据 bookId 过滤
  python import_marknotes_to_anki.py --book-id 3300089819
  
  # 根据书名过滤
  python import_marknotes_to_anki.py --book-name "极简央行课"
  
  # 自动生成 marknotes 文件（如果不存在）
  python import_marknotes_to_anki.py --book-name "极简央行课" --auto-generate
  
  # 先重新 fetch 数据，再自动生成 marknotes
  python import_marknotes_to_anki.py --book-name "极简央行课" --auto-generate --fetch
  
  # 试运行（不实际添加卡片）
  python import_marknotes_to_anki.py --dry-run
  
  # 指定 AnkiConnect 地址
  python import_marknotes_to_anki.py --anki-url http://127.0.0.1:8765
  
  # 指定批量大小
  python import_marknotes_to_anki.py --batch-size 50
        """
    )
    
    parser.add_argument('--file', '--csv-file', dest='csv_file', type=str, default=None,
                       help='要导入的 marknotes CSV 文件路径（可选，如果不指定则导入所有 marknotes 文件）')
    
    # 书籍过滤参数（互斥）
    book_group = parser.add_mutually_exclusive_group()
    book_group.add_argument('--book-id', '--id', dest='book_id', type=str, default=None,
                           help='书籍ID（可选，如果提供则只导入该书籍的 marknotes 文件）')
    book_group.add_argument('--book-name', '--book-title', dest='book_name', type=str, default=None,
                           help='书籍名称（可选，如果提供则只导入该书籍的 marknotes 文件）')
    
    parser.add_argument('--anki-url', dest='anki_url', type=str, default=None,
                       help=f'AnkiConnect API 地址（默认: {ANKI_CONNECT_URL}）')
    parser.add_argument('--model', '--model-name', dest='model_name', type=str, default=None,
                       help=f'Anki 卡牌模板名称（默认: {ANKI_MODEL_NAME}）')
    parser.add_argument('--dry-run', dest='dry_run', action='store_true',
                       help='试运行模式，不实际添加卡片')
    parser.add_argument('--sync', dest='sync', action='store_true',
                       help='导入完成后同步到 AnkiWeb（已弃用：现在总是会自动同步）')
    parser.add_argument('--auto-generate', dest='auto_generate', action='store_true',
                       help='如果找不到 marknotes 文件，自动调用 generate_marknotes.py 生成')
    parser.add_argument('--fetch', '--refresh-data', dest='fetch_data', action='store_true',
                       help='在生成 marknotes 之前，先重新 fetch 笔记数据（需要 --auto-generate）')
    parser.add_argument('--api-key', dest='api_key', type=str, default=None,
                       help='Gemini API 密钥（用于自动生成 marknotes，优先从环境变量 GEMINI_API_KEY 或 GOOGLE_API_KEY 读取）')
    parser.add_argument('--batch-size', dest='batch_size', type=int, default=100,
                       help='批量添加卡片的批次大小（默认: 100，建议范围: 10-200）')
    
    args = parser.parse_args()
    
    # 如果指定了 --fetch 但没有 --auto-generate，提示用户
    if args.fetch_data and not args.auto_generate:
        print("⚠️  警告：--fetch 参数需要配合 --auto-generate 使用")
        print("   将自动启用 --auto-generate")
        args.auto_generate = True
    
    # 获取脚本所在目录
    script_dir = Path(__file__).parent  # anki/scripts
    project_root = script_dir.parent.parent  # 项目根目录
    
    # 默认 marknotes 目录
    marknotes_dir = project_root / "llm" / "output" / "marknotes"
    
    # 初始化 AnkiConnect 客户端
    anki_url = args.anki_url or ANKI_CONNECT_URL
    try:
        anki_client = AnkiConnectClient(url=anki_url)
        # 测试连接
        anki_client._invoke("version")
        print(f"✓ 成功连接到 AnkiConnect ({anki_url})")
    except Exception as e:
        print(f"❌ 无法连接到 AnkiConnect: {e}")
        print(f"\n连接地址: {anki_url}")
        print("\n请确保：")
        print("  1. Anki 正在运行")
        print("  2. 已安装 AnkiConnect 插件")
        print(f"  3. AnkiConnect 配置正确（当前地址: {anki_url}）")
        return
    
    # 确定要处理的文件列表
    csv_files = []
    target_book_id = None
    
    if args.csv_file:
        # 如果指定了文件，只处理该文件
        csv_file = Path(args.csv_file)
        if not csv_file.is_absolute():
            csv_file = project_root / csv_file
        if csv_file.exists():
            csv_files = [csv_file]
        else:
            print(f"❌ 错误：文件不存在: {csv_file}")
            return
    else:
        # 否则处理所有 marknotes 文件
        if not marknotes_dir.exists():
            print(f"❌ 错误：目录不存在: {marknotes_dir}")
            return
        
        # 获取所有 marknotes CSV 文件
        all_csv_files = list(marknotes_dir.glob("*_marknotes.csv"))
        
        if args.book_id:
            target_book_id = args.book_id
            print(f"过滤条件：bookId = {target_book_id}")
        elif args.book_name:
            # 从 fetch_notebooks_output.csv 中查找 bookId
            notebooks_csv = project_root / "wereader" / "output" / "fetch_notebooks_output.csv"
            if notebooks_csv.exists():
                target_book_id = find_book_id_by_title(notebooks_csv, args.book_name)
                if target_book_id:
                    print(f"找到书籍：{args.book_name} (bookId: {target_book_id})")
                else:
                    print(f"❌ 错误：未找到书名 '{args.book_name}' 对应的 bookId")
                    return
            else:
                print(f"❌ 错误：无法查找书名，文件不存在: {notebooks_csv}")
                return
        
        if target_book_id:
            # 根据 bookId 过滤文件（文件名格式：{bookId}_marknotes.csv）
            target_file = marknotes_dir / f"{target_book_id}_marknotes.csv"
            
            # 如果指定了 --fetch，即使文件存在也要重新生成
            if args.fetch_data and args.auto_generate:
                print(f"\n🔄 检测到 --fetch 参数，将先重新 fetch 数据并生成 marknotes...")
                if generate_marknotes is None:
                    print(f"\n❌ 错误：无法导入 generate_marknotes 模块，无法重新生成 marknotes")
                    print(f"请手动运行以下命令重新生成 marknotes：")
                    if args.book_name:
                        print(f"  python llm/scripts/generate_marknotes.py --book-name \"{args.book_name}\" --fetch")
                    else:
                        print(f"  python llm/scripts/generate_marknotes.py --book-id {target_book_id} --fetch")
                    return
                
                print(f"\n🔄 正在重新生成 marknotes CSV 文件（使用最新数据）...")
                try:
                    api_key = args.api_key or os.environ.get('GOOGLE_API_KEY') or os.environ.get('GEMINI_API_KEY')
                    if not api_key:
                        print(f"❌ 错误：未设置 Gemini API 密钥")
                        print(f"请设置环境变量 GEMINI_API_KEY 或 GOOGLE_API_KEY，或使用 --api-key 参数")
                        return
                    
                    # 传递 book_name 以确保 fetch 时能正确使用书名
                    generate_marknotes(book_id=target_book_id, book_title=args.book_name if args.book_name else None, api_key=api_key, fetch_data=True)
                    
                    # 重新检查文件
                    if target_file.exists():
                        csv_files.append(target_file)
                        print(f"✓ 成功重新生成 marknotes CSV 文件")
                    else:
                        print(f"⚠️  生成完成，但未找到对应的 CSV 文件")
                        return
                except Exception as e:
                    print(f"❌ 重新生成 marknotes 失败: {e}")
                    import traceback
                    traceback.print_exc()
                    return
            elif target_file.exists():
                csv_files.append(target_file)
            else:
                print(f"⚠️  未找到 bookId '{target_book_id}' 对应的 marknotes CSV 文件")
                # 如果启用了自动生成，尝试生成
                if args.auto_generate:
                    if generate_marknotes is None:
                        print(f"\n❌ 错误：无法导入 generate_marknotes 模块，无法自动生成 marknotes")
                        print(f"请手动运行以下命令生成 marknotes：")
                        if args.book_name:
                            print(f"  python llm/scripts/generate_marknotes.py --book-name \"{args.book_name}\"")
                        else:
                            print(f"  python llm/scripts/generate_marknotes.py --book-id {target_book_id}")
                        return
                    
                    print(f"\n🔄 正在自动生成 marknotes CSV 文件...")
                    try:
                        api_key = args.api_key or os.environ.get('GOOGLE_API_KEY') or os.environ.get('GEMINI_API_KEY')
                        if not api_key:
                            print(f"❌ 错误：未设置 Gemini API 密钥")
                            print(f"请设置环境变量 GEMINI_API_KEY 或 GOOGLE_API_KEY，或使用 --api-key 参数")
                            return
                        
                        # 如果指定了 --fetch，传递 fetch_data=True，同时传递 book_name 以确保 fetch 时能正确使用书名
                        generate_marknotes(book_id=target_book_id, book_title=args.book_name if args.book_name else None, api_key=api_key, fetch_data=args.fetch_data)
                        
                        # 重新检查文件
                        if target_file.exists():
                            csv_files.append(target_file)
                            print(f"✓ 成功生成 marknotes CSV 文件")
                        else:
                            print(f"⚠️  生成完成，但未找到对应的 CSV 文件")
                            return
                    except Exception as e:
                        print(f"❌ 自动生成 marknotes 失败: {e}")
                        import traceback
                        traceback.print_exc()
                        return
                else:
                    print(f"\n提示：可以使用 --auto-generate 参数自动生成：")
                    print(f"  python anki/scripts/import_marknotes_to_anki.py --book-name \"{args.book_name}\" --auto-generate")
                    return
        else:
            # 处理所有文件
            csv_files = all_csv_files
    
    if not csv_files:
        print("⚠️  没有找到要处理的 CSV 文件")
        return
    
    print(f"\n找到 {len(csv_files)} 个 CSV 文件需要处理")
    
    # 处理每个 CSV 文件
    for csv_file in csv_files:
        try:
            import_csv_to_anki(
                csv_file=csv_file,
                anki_client=anki_client,
                model_name=args.model_name,
                dry_run=args.dry_run,
                sync=args.sync,
                batch_size=args.batch_size
            )
        except Exception as e:
            print(f"❌ 处理文件 {csv_file.name} 时出错: {e}")
            continue
    
    print(f"\n{'='*60}")
    print("所有文件处理完成")
    print(f"{'='*60}")
    
    # 所有文件处理完成后，强制同步到 AnkiWeb
    if not args.dry_run:
        print(f"\n正在同步到 AnkiWeb...")
        if anki_client.sync():
            print(f"✓ 同步成功")
        else:
            print(f"⚠️  同步失败，请稍后手动同步")


if __name__ == "__main__":
    main()
