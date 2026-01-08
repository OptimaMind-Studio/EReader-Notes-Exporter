#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
将 guidebook CSV 文件导入到 Anki
使用 AnkiConnect API 将笔记添加到 Anki
"""

import json
import csv
import requests
import argparse
from pathlib import Path
from typing import Dict, List, Optional
from config import (
    ANKI_CONNECT_URL,
    ANKI_MODEL_NAME,
    DECK_NAME_FORMAT,
    DEFAULT_TAGS,
    FIELD_MAPPING
)


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
    
    def add_note(self, deck_name: str, model_name: str, fields: Dict[str, str], tags: Optional[List[str]] = None) -> int:
        """
        添加单张卡片到 Anki
        
        Args:
            deck_name: 卡牌组名称
            model_name: 卡牌模板名称
            fields: 字段字典（字段名 -> 字段值）
            tags: 标签列表（可选）
        
        Returns:
            新创建的卡片 ID
        """
        note = {
            "deckName": deck_name,
            "modelName": model_name,
            "fields": fields,
        }
        
        if tags:
            note["tags"] = tags
        
        result = self._invoke("addNote", note=note)
        return result
    
    def add_notes(self, notes: List[Dict]) -> List[int]:
        """
        批量添加卡片到 Anki
        
        Args:
            notes: 卡片列表，每个卡片是一个字典，包含 deckName, modelName, fields, tags 等
        
        Returns:
            新创建的卡片 ID 列表
        """
        result = self._invoke("addNotes", notes=notes)
        return result
    
    def find_notes(self, query: str) -> List[int]:
        """
        查找卡片
        
        Args:
            query: 查询字符串
        
        Returns:
            卡片 ID 列表
        """
        return self._invoke("findNotes", query=query)
    
    def notes_info(self, notes: List[int]) -> List[Dict]:
        """
        获取卡片信息
        
        Args:
            notes: 卡片 ID 列表
        
        Returns:
            卡片信息列表
        """
        return self._invoke("notesInfo", notes=notes)
    
    def deck_names(self) -> List[str]:
        """
        获取所有卡牌组名称列表
        
        Returns:
            卡牌组名称列表
        """
        return self._invoke("deckNames")
    
    def create_deck(self, deck_name: str) -> int:
        """
        创建卡牌组
        
        Args:
            deck_name: 卡牌组名称
        
        Returns:
            创建的卡牌组 ID
        """
        return self._invoke("createDeck", deck=deck_name)
    
    def deck_exists(self, deck_name: str) -> bool:
        """
        检查卡牌组是否存在
        
        Args:
            deck_name: 卡牌组名称
        
        Returns:
            如果存在返回 True，否则返回 False
        """
        try:
            decks = self.deck_names()
            return deck_name in decks
        except Exception:
            return False
    
    def ensure_deck_exists(self, deck_name: str) -> bool:
        """
        确保卡牌组存在，如果不存在则创建
        
        Args:
            deck_name: 卡牌组名称
        
        Returns:
            如果成功返回 True，否则返回 False
        """
        if self.deck_exists(deck_name):
            return True
        
        try:
            self.create_deck(deck_name)
            return True
        except Exception as e:
            print(f"  ⚠️  创建卡牌组失败: {e}")
            return False
    
    def find_duplicate_notes(self, deck_name: str, model_name: str, fields: Dict[str, str]) -> List[int]:
        """
        查找重复的卡片（基于第一个字段的值）
        
        Args:
            deck_name: 卡牌组名称
            model_name: 卡牌模板名称
            fields: 字段字典
        
        Returns:
            重复卡片的 ID 列表
        """
        # 使用第一个字段的值来查找重复卡片
        if not fields:
            return []
        
        first_field_value = list(fields.values())[0] if fields else ""
        if not first_field_value:
            return []
        
        # 构建查询：查找相同卡牌组、相同模板、相同第一个字段值的卡片
        # 转义特殊字符
        escaped_deck_name = deck_name.replace('"', '\\"')
        escaped_field_value = first_field_value.replace('"', '\\"')
        query = f'deck:"{escaped_deck_name}" note:"{model_name}" "{escaped_field_value}"'
        try:
            return self.find_notes(query)
        except Exception:
            return []
    
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
            error_msg = str(e)
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
    """
    读取 CSV 文件
    
    Args:
        csv_file: CSV 文件路径
    
    Returns:
        数据行列表
    """
    rows = []
    try:
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
        return rows
    except Exception as e:
        print(f"错误：读取 CSV 文件失败 {csv_file}: {e}")
        return []


def get_book_title_from_csv(csv_file: Path) -> Optional[str]:
    """
    从 CSV 文件中获取书名（从第一行的 title 字段）
    
    Args:
        csv_file: CSV 文件路径
    
    Returns:
        书名，如果未找到则返回 None
    """
    rows = read_csv_file(csv_file)
    if rows and 'title' in rows[0]:
        return rows[0]['title'].strip()
    return None


def map_csv_fields_to_anki_fields(csv_row: Dict[str, str], field_mapping: Dict[str, str]) -> Dict[str, str]:
    """
    将 CSV 行数据映射到 Anki 字段
    
    Args:
        csv_row: CSV 行数据（字典）
        field_mapping: 字段映射关系（CSV 列名 -> Anki 字段名）
    
    Returns:
        Anki 字段字典
    """
    anki_fields = {}
    
    for csv_field, anki_field in field_mapping.items():
        if csv_field in csv_row:
            value = csv_row[csv_field]
            
            # 特殊处理：如果是 explanation 字段（映射到 AINotes），去除首尾引号
            if csv_field == 'explanation' and anki_field == 'AINotes':
                # 去除开头和结尾的引号（单引号或双引号）
                value = value.strip()
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]
                # 确保是 HTML 格式（如果还不是完整的 HTML，可能需要包装）
                value = value.strip()
            
            anki_fields[anki_field] = value
        else:
            # 如果 CSV 中没有该字段，设置为空字符串
            anki_fields[anki_field] = ""
    
    return anki_fields


def import_csv_to_anki(csv_file: Path, anki_client: AnkiConnectClient, model_name: Optional[str] = None, 
                       field_mapping: Optional[Dict[str, str]] = None, dry_run: bool = False, sync: bool = False):
    """
    将 CSV 文件导入到 Anki
    
    Args:
        csv_file: CSV 文件路径
        anki_client: AnkiConnect 客户端
        model_name: Anki 卡牌模板名称（默认: KWDict）
        field_mapping: 字段映射关系（如果为 None，使用默认映射）
        dry_run: 是否为试运行（不实际添加卡片）
    """
    if field_mapping is None:
        field_mapping = FIELD_MAPPING
    
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
    deck_name = DECK_NAME_FORMAT.format(book_title=book_title)
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
        
        # 检查必填字段（Name 字段）
        if 'Name' in anki_fields and not anki_fields['Name'].strip():
            skipped_count += 1
            continue
        
        # 检查是否已存在重复卡片（基于 Name 字段）
        if 'Name' in anki_fields:
            duplicate_notes = anki_client.find_duplicate_notes(deck_name, model_name, anki_fields)
            if duplicate_notes:
                duplicate_count += 1
                continue
        
        # 构建卡片数据
        note = {
            "deckName": deck_name,
            "modelName": model_name,
            "fields": anki_fields,
            "tags": DEFAULT_TAGS
        }
        
        notes_to_add.append(note)
    
    if skipped_count > 0:
        print(f"跳过 {skipped_count} 条记录（缺少必填字段）")
    if duplicate_count > 0:
        print(f"跳过 {duplicate_count} 条记录（已存在的重复卡片）")
    
    if not notes_to_add:
        print("没有有效的记录需要添加")
        # 即使没有新卡片，如果指定了 --sync，也要执行同步
        if sync:
            print(f"\n正在同步到 AnkiWeb...")
            if anki_client.sync():
                print(f"✓ 同步成功")
            else:
                print(f"⚠️  同步失败，请稍后手动同步")
        return
    
    print(f"\n准备添加 {len(notes_to_add)} 张卡片...")
    
    if dry_run:
        print("🔍 试运行模式：不会实际添加卡片")
        print(f"示例卡片（第一条）:")
        print(json.dumps(notes_to_add[0], ensure_ascii=False, indent=2))
        # 试运行模式下，如果指定了 --sync，也要执行同步
        if sync:
            print(f"\n正在同步到 AnkiWeb...")
            if anki_client.sync():
                print(f"✓ 同步成功")
            else:
                print(f"⚠️  同步失败，请稍后手动同步")
        return
    
    # 批量添加卡片（每次最多 100 张，避免请求过大）
    batch_size = 100
    total_added = 0
    
    for i in range(0, len(notes_to_add), batch_size):
        batch = notes_to_add[i:i + batch_size]
        try:
            result = anki_client.add_notes(batch)
            # result 是一个列表，包含成功添加的卡片 ID 和 None（失败的）
            added_count = sum(1 for x in result if x is not None)
            total_added += added_count
            print(f"  批次 {i//batch_size + 1}: 成功添加 {added_count}/{len(batch)} 张卡片")
        except Exception as e:
            print(f"  ❌ 批次 {i//batch_size + 1} 添加失败: {e}")
    
    print(f"\n✓ 完成！共添加 {total_added}/{len(notes_to_add)} 张卡片到 Anki")
    
    # 如果需要同步到 AnkiWeb
    if sync:
        print(f"\n正在同步到 AnkiWeb...")
        if anki_client.sync():
            print(f"✓ 同步成功")
        else:
            print(f"⚠️  同步失败，请稍后手动同步")


def find_book_id_by_title(csv_file: Path, book_title: str) -> Optional[str]:
    """
    根据书名在 CSV 文件中查找 bookId
    
    Args:
        csv_file: CSV 文件路径
        book_title: 书名
    
    Returns:
        bookId，如果未找到则返回 None
    """
    try:
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                title = row.get('title', '').strip()
                if title == book_title:
                    return row.get('bookId', '').strip()
        return None
    except Exception as e:
        print(f"错误：读取 CSV 文件失败: {e}")
        return None


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='将 guidebook CSV 文件导入到 Anki',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  # 导入所有 guidebook CSV 文件
  python import_guidebook_to_anki.py
  
  # 导入指定的 CSV 文件
  python import_guidebook_to_anki.py --file llm/output/guidebook/3300089819_all_chapters_guidebook.csv
  
  # 根据 bookId 过滤
  python import_guidebook_to_anki.py --book-id 3300089819
  
  # 根据书名过滤
  python import_guidebook_to_anki.py --book-name "极简央行课"
  
  # 试运行（不实际添加卡片）
  python import_guidebook_to_anki.py --dry-run
  
  # 指定 AnkiConnect 地址
  python import_guidebook_to_anki.py --anki-url http://127.0.0.1:8765
        """
    )
    
    parser.add_argument('--file', '--csv-file', dest='csv_file', type=str, default=None,
                       help='要导入的 CSV 文件路径（可选，如果不指定则导入所有 guidebook CSV 文件）')
    
    # 书籍过滤参数（互斥）
    book_group = parser.add_mutually_exclusive_group()
    book_group.add_argument('--book-id', '--id', dest='book_id', type=str, default=None,
                           help='书籍ID（可选，如果提供则只导入该书籍的 CSV 文件）')
    book_group.add_argument('--book-name', '--title', dest='book_name', type=str, default=None,
                           help='书籍名称（可选，如果提供则只导入该书籍的 CSV 文件）')
    
    parser.add_argument('--anki-url', dest='anki_url', type=str, default=None,
                       help=f'AnkiConnect API 地址（默认: {ANKI_CONNECT_URL}）')
    parser.add_argument('--model', '--model-name', dest='model_name', type=str, default=None,
                       help=f'Anki 卡牌模板名称（默认: {ANKI_MODEL_NAME}）')
    parser.add_argument('--dry-run', dest='dry_run', action='store_true',
                       help='试运行模式，不实际添加卡片')
    parser.add_argument('--sync', dest='sync', action='store_true',
                       help='导入完成后同步到 AnkiWeb')
    
    args = parser.parse_args()
    
    # 获取脚本所在目录
    script_dir = Path(__file__).parent  # anki/scripts
    project_root = script_dir.parent.parent  # 项目根目录
    
    # 默认 guidebook 目录
    guidebook_dir = project_root / "llm" / "output" / "guidebook"
    
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
        # 否则处理所有 guidebook CSV 文件
        if not guidebook_dir.exists():
            print(f"❌ 错误：目录不存在: {guidebook_dir}")
            return
        
        # 如果指定了 book_id 或 book_name，先确定目标 bookId
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
        
        # 获取所有 CSV 文件
        all_csv_files = list(guidebook_dir.glob("*.csv"))
        
        if target_book_id:
            # 根据 bookId 过滤文件（文件名格式：{bookId}_{chapter}_guidebook.csv 或 {bookId}_all_chapters_guidebook.csv）
            csv_files = [f for f in all_csv_files if f.stem.startswith(f"{target_book_id}_")]
            if not csv_files:
                print(f"⚠️  未找到 bookId '{target_book_id}' 对应的 CSV 文件")
                return
            print(f"找到 {len(csv_files)} 个匹配的 CSV 文件（bookId: {target_book_id}）")
        else:
            csv_files = all_csv_files
            if not csv_files:
                print(f"⚠️  未找到 CSV 文件: {guidebook_dir}")
                return
            print(f"找到 {len(csv_files)} 个 CSV 文件")
    
    # 依次处理每个 CSV 文件
    for csv_file in csv_files:
        try:
            import_csv_to_anki(
                csv_file=csv_file,
                anki_client=anki_client,
                model_name=args.model_name or ANKI_MODEL_NAME,
                field_mapping=FIELD_MAPPING,
                dry_run=args.dry_run,
                sync=args.sync
            )
        except Exception as e:
            print(f"❌ 处理文件 {csv_file.name} 时出错: {e}")
            import traceback
            traceback.print_exc()
    
    print(f"\n{'='*60}")
    print("所有文件处理完成")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()

