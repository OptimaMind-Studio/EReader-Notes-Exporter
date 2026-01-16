#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
将 concepts CSV 文件导入到 Anki
使用 AnkiConnect API 将概念卡片添加到 Anki
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
    DEFAULT_TAGS,
    CONCEPTS_DECK_NAME_FORMAT,
    CONCEPTS_FIELD_MAPPING
)

# 导入 extract_concepts 模块
try:
    # 从项目根目录运行时
    script_dir = Path(__file__).parent  # anki/scripts
    project_root = script_dir.parent.parent  # 项目根目录
    sys.path.insert(0, str(project_root))
    from llm.scripts.extract_concepts import process_csv_file as generate_concepts
except (ImportError, ModuleNotFoundError) as e:
    # 如果导入失败，尝试直接导入
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent.parent / "llm" / "scripts"))
        from extract_concepts import process_csv_file as generate_concepts
    except (ImportError, ModuleNotFoundError) as e2:
        # 导入失败，可能是依赖缺失（如 google-generativeai）
        generate_concepts = None
        # 不在这里打印错误，让调用方处理


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
            "tags": tags or []
        }
        result = self._invoke("addNote", note=note)
        return result
    
    def add_notes(self, notes: List[Dict]) -> List[Optional[int]]:
        """
        批量添加卡片到 Anki
        
        Args:
            notes: 卡片列表，每个卡片是一个字典，包含 deckName, modelName, fields, tags
        
        Returns:
            新创建的卡片 ID 列表（如果失败则为 None）
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
            卡牌组 ID
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
        decks = self.deck_names()
        return deck_name in decks
    
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
        查找重复的卡片（基于 Name 字段的值，即概念词）
        
        Args:
            deck_name: 卡牌组名称
            model_name: 卡牌模板名称
            fields: 字段字典
        
        Returns:
            重复卡片的 ID 列表
        """
        # 优先使用 Name 字段（概念词）来查找重复卡片
        if not fields:
            return []
        
        # 优先使用 Name 字段，如果没有则使用第一个字段
        name_field_value = fields.get('Name', '')
        if not name_field_value:
            # 如果没有 Name 字段，尝试使用第一个字段
            name_field_value = list(fields.values())[0] if fields else ""
        
        if not name_field_value:
            return []
        
        # 构建查询：查找相同卡牌组、相同模板、相同 Name 字段值的卡片
        # 转义特殊字符（Anki 查询语法需要转义引号、冒号等）
        escaped_deck_name = deck_name.replace('"', '\\"').replace(':', '\\:')
        escaped_model_name = model_name.replace('"', '\\"')
        # 转义查询值中的特殊字符
        escaped_field_value = name_field_value.replace('"', '\\"').replace('\\', '\\\\')
        
        # 使用更精确的查询：deck:卡牌组名 note:模板名 "Name字段值"
        # 注意：Anki 查询中，字段名需要用引号包裹，值也需要用引号包裹
        query = f'deck:"{escaped_deck_name}" note:"{escaped_model_name}" "Name:{escaped_field_value}"'
        try:
            notes = self.find_notes(query)
            # 如果上面的查询没找到，尝试更简单的查询（只基于字段值）
            if not notes:
                query_simple = f'deck:"{escaped_deck_name}" note:"{escaped_model_name}" {escaped_field_value}'
                notes = self.find_notes(query_simple)
            return notes
        except Exception as e:
            # 如果查询失败，返回空列表（不阻止添加）
            print(f"  ⚠️  查询重复卡片时出错: {e}")
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


def get_book_title_from_concepts_csv(csv_file: Path) -> Optional[str]:
    """
    从 concepts CSV 文件中获取书名（从第一行的 source 字段）
    
    Args:
        csv_file: CSV 文件路径
    
    Returns:
        书名，如果未找到则返回 None
    """
    rows = read_csv_file(csv_file)
    if rows and 'source' in rows[0]:
        return rows[0]['source'].strip()
    return None


def get_chapter_name_mapping(book_id: str, project_root: Path) -> Dict[int, str]:
    """
    从笔记 CSV 文件中获取章节号到章节名称的映射
    
    Args:
        book_id: 书籍ID
        project_root: 项目根目录
    
    Returns:
        章节号到章节名称的字典
    """
    chapter_mapping = {}
    
    # 尝试从 bookmarks CSV 文件中读取章节名称
    bookmarks_file = project_root / "wereader" / "output" / "bookmarks" / f"{book_id}.csv"
    if bookmarks_file.exists():
        try:
            with open(bookmarks_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    chapter_uid = row.get('chapterUid', '').strip()
                    chapter_name = row.get('chapterName', '').strip()
                    if chapter_uid and chapter_name:
                        try:
                            chapter_uid_int = int(chapter_uid)
                            if chapter_uid_int not in chapter_mapping:
                                chapter_mapping[chapter_uid_int] = chapter_name
                        except ValueError:
                            pass
        except Exception as e:
            print(f"  ⚠️  读取章节名称映射失败: {e}")
    
    return chapter_mapping


def format_chapter_range(chapter_range: str, chapter_mapping: Dict[int, str]) -> str:
    """
    将章节范围字符串（如 "191" 或 "191-197"）转换为"章节号-章节名"格式
    
    Args:
        chapter_range: 章节范围字符串（如 "191" 或 "191-197"）
        chapter_mapping: 章节号到章节名称的映射
    
    Returns:
        格式化后的字符串（如 "191-赞誉" 或 "191-赞誉-197-总结"）
    """
    if not chapter_range or not chapter_range.strip():
        return ""
    
    chapter_range = chapter_range.strip()
    
    # 解析章节范围（可能是单个章节号或范围）
    if '-' in chapter_range:
        # 范围格式：如 "191-197"
        parts = chapter_range.split('-')
        if len(parts) == 2:
            try:
                start_chapter = int(parts[0].strip())
                end_chapter = int(parts[1].strip())
                start_name = chapter_mapping.get(start_chapter, f'章节{start_chapter}')
                end_name = chapter_mapping.get(end_chapter, f'章节{end_chapter}')
                return f"{start_chapter}-{start_name}-{end_chapter}-{end_name}"
            except ValueError:
                return chapter_range
        else:
            return chapter_range
    else:
        # 单个章节号：如 "191"
        try:
            chapter_num = int(chapter_range)
            chapter_name = chapter_mapping.get(chapter_num, f'章节{chapter_num}')
            return f"{chapter_num}-{chapter_name}"
        except ValueError:
            return chapter_range


def map_csv_fields_to_anki_fields(csv_row: Dict[str, str], field_mapping: Dict[str, str], 
                                   chapter_mapping: Optional[Dict[int, str]] = None) -> Dict[str, str]:
    """
    将 CSV 行数据映射到 Anki 字段
    
    Args:
        csv_row: CSV 行数据（字典）
        field_mapping: 字段映射关系（CSV 列名 -> Anki 字段名）
        chapter_mapping: 章节号到章节名称的映射（可选）
    
    Returns:
        Anki 字段字典
    """
    anki_fields = {}
    
    for csv_field, anki_field in field_mapping.items():
        if csv_field in csv_row:
            value = csv_row[csv_field]
            
            # 特殊处理：如果是 definition 字段（映射到 AINotes），去除首尾引号
            if csv_field == 'definition' and anki_field == 'AINotes':
                # 去除开头和结尾的引号（单引号或双引号）
                value = value.strip()
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]
                # 确保是 HTML 格式
                value = value.strip()
            
            # 特殊处理：如果是 chapterRange 字段（映射到 References），转换为"章节号-章节名"格式
            elif csv_field == 'chapterRange' and anki_field == 'References':
                if chapter_mapping:
                    value = format_chapter_range(value, chapter_mapping)
                else:
                    # 如果没有章节映射，保持原值
                    value = value.strip()
            
            anki_fields[anki_field] = value
        else:
            # 如果 CSV 中没有该字段，设置为空字符串
            anki_fields[anki_field] = ""
    
    return anki_fields


def import_csv_to_anki(csv_file: Path, anki_client: AnkiConnectClient, model_name: Optional[str] = None, 
                       field_mapping: Optional[Dict[str, str]] = None, dry_run: bool = False, sync: bool = False,
                       batch_size: int = 100):
    """
    将 concepts CSV 文件导入到 Anki
    
    Args:
        csv_file: CSV 文件路径
        anki_client: AnkiConnect 客户端
        model_name: Anki 卡牌模板名称（默认: KWDict）
        field_mapping: 字段映射关系（如果为 None，使用默认映射）
        dry_run: 是否为试运行（不实际添加卡片）
        sync: 是否同步到 AnkiWeb
        batch_size: 批量添加的批次大小（默认: 100）
    """
    if field_mapping is None:
        field_mapping = CONCEPTS_FIELD_MAPPING
    
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
    
    # 获取书名（从第一行的 source 字段）
    book_title = get_book_title_from_concepts_csv(csv_file)
    if not book_title:
        print(f"⚠️  无法获取书名，跳过")
        return
    
    # 从文件名中提取 book_id（格式：{book_id}_concepts.csv）
    book_id = None
    file_stem = csv_file.stem  # 例如：38894783_concepts
    if '_concepts' in file_stem:
        book_id = file_stem.split('_concepts')[0]
    elif '_' in file_stem:
        # 如果没有 _concepts，尝试提取第一个下划线前的部分
        book_id = file_stem.split('_')[0]
    
    # 获取章节名称映射
    chapter_mapping = {}
    if book_id:
        script_dir = Path(__file__).parent  # anki/scripts
        project_root = script_dir.parent.parent  # 项目根目录
        chapter_mapping = get_chapter_name_mapping(book_id, project_root)
        if chapter_mapping:
            print(f"✓ 已加载 {len(chapter_mapping)} 个章节名称映射")
    
    # 构建卡牌组名称（使用配置中的格式）
    deck_name = CONCEPTS_DECK_NAME_FORMAT.format(book_title=book_title)
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
        # 映射字段（传入章节映射）
        anki_fields = map_csv_fields_to_anki_fields(row, field_mapping, chapter_mapping)
        
        # 检查必填字段（Name 字段，对应 concept）
        if 'Name' in anki_fields and not anki_fields['Name'].strip():
            skipped_count += 1
            continue
        
        # 检查是否已存在重复卡片（基于 Name 字段，即 concept）
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
            "tags": DEFAULT_TAGS + ["concepts"]
        }
        
        notes_to_add.append(note)
    
    if skipped_count > 0:
        print(f"跳过 {skipped_count} 条记录（缺少必填字段）")
    if duplicate_count > 0:
        print(f"跳过 {duplicate_count} 条记录（已存在的重复卡片）")
    
    if not notes_to_add:
        print("没有有效的记录需要添加")
        # 注意：同步操作延迟到所有文件处理完成后统一执行
        return
    
    print(f"\n准备添加 {len(notes_to_add)} 张卡片...")
    
    if dry_run:
        print("🔍 试运行模式：不会实际添加卡片")
        print(f"示例卡片（第一条）:")
        print(json.dumps(notes_to_add[0], ensure_ascii=False, indent=2))
        # 注意：同步操作延迟到所有文件处理完成后统一执行
        return
    
    # 批量添加卡片（使用传入的 batch_size 参数）
    total_added = 0
    total_failed = 0
    
    for i in range(0, len(notes_to_add), batch_size):
        batch = notes_to_add[i:i + batch_size]
        try:
            result = anki_client.add_notes(batch)
            # result 是一个列表，包含成功添加的卡片 ID 和 None（失败的）
            added_count = sum(1 for x in result if x is not None)
            failed_count = len(batch) - added_count
            total_added += added_count
            total_failed += failed_count
            if failed_count > 0:
                print(f"  批次 {i//batch_size + 1}: 成功添加 {added_count}/{len(batch)} 张卡片（{failed_count} 张可能重复）")
            else:
                print(f"  批次 {i//batch_size + 1}: 成功添加 {added_count}/{len(batch)} 张卡片")
        except Exception as e:
            error_msg = str(e)
            # 如果批量添加失败，改为逐个添加（无论是什么错误）
            print(f"  批次 {i//batch_size + 1}: 批量添加失败，改为逐个添加...")
            batch_added = 0
            batch_failed = 0
            batch_duplicate = 0
            
            for note_idx, note in enumerate(batch, 1):
                try:
                    note_id = anki_client.add_note(
                        deck_name=note['deckName'],
                        model_name=note['modelName'],
                        fields=note['fields'],
                        tags=note.get('tags', [])
                    )
                    if note_id:
                        batch_added += 1
                except Exception as note_error:
                    error_str = str(note_error).lower()
                    if 'duplicate' in error_str:
                        # 重复的卡片，跳过
                        batch_duplicate += 1
                        batch_failed += 1
                    else:
                        # 其他错误，打印详细信息
                        concept_name = note['fields'].get('Name', '未知')[:50]
                        print(f"    [{note_idx}/{len(batch)}] ⚠️  添加卡片失败 ({concept_name}...): {note_error}")
                        batch_failed += 1
            
            total_added += batch_added
            total_failed += batch_failed
            
            # 打印汇总信息
            if batch_added > 0 or batch_failed > 0:
                status_parts = []
                if batch_added > 0:
                    status_parts.append(f"成功 {batch_added}")
                if batch_duplicate > 0:
                    status_parts.append(f"重复 {batch_duplicate}")
                if batch_failed > batch_duplicate:
                    status_parts.append(f"失败 {batch_failed - batch_duplicate}")
                status_str = "，".join(status_parts)
                print(f"  批次 {i//batch_size + 1}: 逐个添加完成（{status_str}/{len(batch)} 张卡片）")
            else:
                print(f"  批次 {i//batch_size + 1}: 逐个添加完成，成功 {batch_added}/{len(batch)} 张卡片")
    
    print(f"\n✓ 完成！共添加 {total_added}/{len(notes_to_add)} 张卡片到 Anki")
    if total_failed > 0:
        print(f"⚠️  跳过 {total_failed} 张卡片（可能是重复卡片）")
    
    # 注意：同步操作延迟到所有文件处理完成后统一执行


def find_book_id_by_title(csv_file: Path, book_title: str) -> Optional[str]:
    """
    根据书名在 CSV 文件中查找 bookId
    支持精确匹配和部分匹配（如果书名包含在 CSV 的 title 字段中，或 CSV 的 title 包含在输入的书名中）
    
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
        description='将 concepts CSV 文件导入到 Anki',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  # 导入所有 concepts CSV 文件
  python import_concepts_to_anki.py
  
  # 导入指定的 CSV 文件
  python import_concepts_to_anki.py --file llm/output/concepts/3300089819_concepts.csv
  
  # 根据 bookId 过滤
  python import_concepts_to_anki.py --book-id 3300089819
  
  # 根据书名过滤
  python import_concepts_to_anki.py --title "极简央行课"
  
  # 自动生成 concepts CSV 文件（如果不存在）
  python import_concepts_to_anki.py --title "极简央行课" --auto-generate
  
  # 自动生成并指定 API key
  python import_concepts_to_anki.py --title "极简央行课" --auto-generate --api-key YOUR_API_KEY
  
  # 试运行（不实际添加卡片）
  python import_concepts_to_anki.py --dry-run
  
  # 指定 AnkiConnect 地址
  python import_concepts_to_anki.py --anki-url http://127.0.0.1:8765
  
  # 导入后自动同步到 AnkiWeb
  python import_concepts_to_anki.py --sync
  
  # 指定批量大小（每批30张卡片）
  python import_concepts_to_anki.py --batch-size 30
        """
    )
    
    parser.add_argument('--file', '--csv-file', dest='csv_file', type=str, default=None,
                       help='要导入的 CSV 文件路径（可选，如果不指定则导入所有 concepts CSV 文件）')
    
    # 书籍过滤参数（互斥）
    book_group = parser.add_mutually_exclusive_group()
    book_group.add_argument('--book-id', '--id', dest='book_id', type=str, default=None,
                           help='书籍ID（可选，如果提供则只导入该书籍的 CSV 文件）')
    book_group.add_argument('--title', '--book-title', '--book-name', dest='book_name', type=str, default=None,
                           help='书籍名称（可选，如果提供则只导入该书籍的 CSV 文件）')
    
    parser.add_argument('--anki-url', type=str, default=None,
                       help=f'AnkiConnect API 地址（默认: {ANKI_CONNECT_URL}）')
    parser.add_argument('--model', '--model-name', dest='model_name', type=str, default=None,
                       help=f'Anki 卡牌模板名称（默认: {ANKI_MODEL_NAME}）')
    parser.add_argument('--dry-run', dest='dry_run', action='store_true',
                       help='试运行模式：不实际添加卡片，只显示将要添加的内容')
    parser.add_argument('--sync', dest='sync', action='store_true',
                       help='导入后自动同步到 AnkiWeb（已弃用：现在总是会自动同步）')
    parser.add_argument('--auto-generate', dest='auto_generate', action='store_true',
                       help='如果找不到 concepts CSV 文件，自动调用 extract_concepts.py 生成')
    parser.add_argument('--fetch', '--refresh-data', dest='fetch_data', action='store_true',
                       help='在生成 concepts 之前，先重新 fetch 笔记数据（调用 wereader/fetch.py）')
    parser.add_argument('--api-key', dest='api_key', type=str, default=None,
                       help='Gemini API 密钥（用于自动生成 concepts，优先从环境变量 GEMINI_API_KEY 或 GOOGLE_API_KEY 读取）')
    parser.add_argument('--batch-size', dest='batch_size', type=int, default=100,
                       help='批量添加卡片的批次大小（默认: 100，建议范围: 10-200）')
    
    args = parser.parse_args()
    
    # 获取项目根目录
    script_dir = Path(__file__).parent  # anki/scripts
    project_root = script_dir.parent.parent  # 项目根目录
    
    # 默认路径
    concepts_dir = project_root / "llm" / "output" / "concepts"
    books_csv = project_root / "wereader" / "output" / "fetch_notebooks_output.csv"
    
    # 创建 AnkiConnect 客户端
    try:
        anki_client = AnkiConnectClient(url=args.anki_url)
        print("✓ 成功连接到 AnkiConnect")
    except Exception as e:
        print(f"❌ 错误：无法连接到 AnkiConnect: {e}")
        return
    
    # 确定要处理的 CSV 文件列表
    csv_files = []
    
    if args.csv_file:
        # 如果指定了文件路径，只处理该文件
        csv_file = Path(args.csv_file)
        if not csv_file.is_absolute():
            csv_file = project_root / csv_file
        if csv_file.exists():
            csv_files.append(csv_file)
        else:
            print(f"❌ 错误：文件不存在: {csv_file}")
            return
    else:
        # 如果没有指定文件，处理所有 concepts CSV 文件
        if not concepts_dir.exists():
            print(f"❌ 错误：目录不存在: {concepts_dir}")
            return
        
        # 获取所有 CSV 文件
        all_csv_files = list(concepts_dir.glob("*.csv"))
        
        if args.book_id:
            # 根据 bookId 过滤
            target_file = concepts_dir / f"{args.book_id}_concepts.csv"
            # 如果指定了 --fetch，即使找到了文件，也要先 fetch 并重新生成
            if args.fetch_data and args.auto_generate:
                print(f"\n🔄 检测到 --fetch 参数，将先重新 fetch 数据并生成 concepts...")
                if generate_concepts is None:
                    print(f"\n❌ 错误：无法导入 extract_concepts 模块，无法重新生成 concepts")
                    print(f"可能的原因：")
                    print(f"  1. 缺少依赖模块（如 google-generativeai）")
                    print(f"     请运行: pip install google-generativeai")
                    print(f"  2. Python 路径配置问题")
                    print(f"\n请手动运行以下命令重新生成 concepts：")
                    print(f"  python llm/scripts/extract_concepts.py --book-name \"{args.book_name or 'BOOK_NAME'}\" --fetch")
                    return
                
                print(f"\n🔄 正在重新生成 concepts CSV 文件（使用最新数据）...")
                try:
                    api_key = args.api_key or os.environ.get('GOOGLE_API_KEY') or os.environ.get('GEMINI_API_KEY')
                    if not api_key:
                        print(f"❌ 错误：未设置 Gemini API 密钥")
                        print(f"请设置环境变量 GEMINI_API_KEY 或 GOOGLE_API_KEY，或使用 --api-key 参数")
                        return
                    
                    generate_concepts(book_id=args.book_id, api_key=api_key, fetch_data=True)
                    
                    # 重新检查文件
                    if target_file.exists():
                        csv_files.append(target_file)
                        print(f"✓ 成功重新生成 concepts CSV 文件")
                    else:
                        print(f"⚠️  生成完成，但未找到对应的 CSV 文件")
                        return
                except Exception as e:
                    print(f"❌ 重新生成 concepts 失败: {e}")
                    import traceback
                    traceback.print_exc()
                    return
            elif target_file.exists():
                csv_files.append(target_file)
            else:
                print(f"⚠️  未找到 bookId '{args.book_id}' 对应的 concepts CSV 文件")
                # 如果启用了自动生成，尝试生成
                if args.auto_generate:
                    if generate_concepts is None:
                        print(f"\n❌ 错误：无法导入 extract_concepts 模块，无法自动生成 concepts")
                        print(f"可能的原因：")
                        print(f"  1. 缺少依赖模块（如 google-generativeai）")
                        print(f"     请运行: pip install google-generativeai")
                        print(f"  2. Python 路径配置问题")
                        print(f"\n请手动运行以下命令生成 concepts：")
                        print(f"  python llm/scripts/extract_concepts.py --book-id {args.book_id}")
                        return
                    
                    print(f"\n🔄 正在自动生成 concepts CSV 文件...")
                    try:
                        api_key = args.api_key or os.environ.get('GOOGLE_API_KEY') or os.environ.get('GEMINI_API_KEY')
                        if not api_key:
                            print(f"❌ 错误：未设置 Gemini API 密钥")
                            print(f"请设置环境变量 GEMINI_API_KEY 或 GOOGLE_API_KEY，或使用 --api-key 参数")
                            return
                        
                        generate_concepts(book_id=args.book_id, api_key=api_key, fetch_data=args.fetch_data)
                        
                        # 重新检查文件
                        if target_file.exists():
                            csv_files.append(target_file)
                            print(f"✓ 成功生成 concepts CSV 文件")
                        else:
                            print(f"⚠️  生成完成，但未找到对应的 CSV 文件")
                            return
                    except Exception as e:
                        print(f"❌ 自动生成 concepts 失败: {e}")
                        import traceback
                        traceback.print_exc()
                        return
                else:
                    print(f"\n提示：可以使用 --auto-generate 参数自动生成：")
                    print(f"  python anki/scripts/import_concepts_to_anki.py --book-id {args.book_id} --auto-generate")
                    return
        elif args.book_name:
            # 根据书名过滤
            if not books_csv.exists():
                print(f"❌ 错误：无法查找书名对应的 bookId，书籍列表文件不存在: {books_csv}")
                return
            
            book_id = find_book_id_by_title(books_csv, args.book_name)
            if book_id:
                target_file = concepts_dir / f"{book_id}_concepts.csv"
                # 如果指定了 --fetch，即使找到了文件，也要先 fetch 并重新生成
                if args.fetch_data and args.auto_generate:
                    print(f"\n🔄 检测到 --fetch 参数，将先重新 fetch 数据并生成 concepts...")
                    if generate_concepts is None:
                        print(f"\n❌ 错误：无法导入 extract_concepts 模块，无法重新生成 concepts")
                        print(f"可能的原因：")
                        print(f"  1. 缺少依赖模块（如 google-generativeai）")
                        print(f"     请运行: pip install google-generativeai")
                        print(f"  2. Python 路径配置问题")
                        print(f"\n请手动运行以下命令重新生成 concepts：")
                        print(f"  python llm/scripts/extract_concepts.py --book-name \"{args.book_name}\" --fetch")
                        return
                    
                    print(f"\n🔄 正在重新生成 concepts CSV 文件（使用最新数据）...")
                    try:
                        api_key = args.api_key or os.environ.get('GOOGLE_API_KEY') or os.environ.get('GEMINI_API_KEY')
                        if not api_key:
                            print(f"❌ 错误：未设置 Gemini API 密钥")
                            print(f"请设置环境变量 GEMINI_API_KEY 或 GOOGLE_API_KEY，或使用 --api-key 参数")
                            return
                        
                        # 直接使用已找到的 bookId，避免重复查找
                        generate_concepts(book_id=book_id, api_key=api_key, fetch_data=True)
                        
                        # 重新检查文件
                        if target_file.exists():
                            csv_files.append(target_file)
                            print(f"✓ 成功重新生成 concepts CSV 文件")
                        else:
                            print(f"⚠️  生成完成，但未找到对应的 CSV 文件")
                            return
                    except Exception as e:
                        print(f"❌ 重新生成 concepts 失败: {e}")
                        import traceback
                        traceback.print_exc()
                        return
                elif target_file.exists():
                    csv_files.append(target_file)
                else:
                    print(f"⚠️  未找到书名 '{args.book_name}' 对应的 concepts CSV 文件")
                    # 如果启用了自动生成，尝试生成
                    if args.auto_generate:
                        if generate_concepts is None:
                            print(f"\n❌ 错误：无法导入 extract_concepts 模块，无法自动生成 concepts")
                            print(f"可能的原因：")
                            print(f"  1. 缺少依赖模块（如 google-generativeai）")
                            print(f"     请运行: pip install google-generativeai")
                            print(f"  2. Python 路径配置问题")
                            print(f"\n请手动运行以下命令生成 concepts：")
                            print(f"  python llm/scripts/extract_concepts.py --book-name \"{args.book_name}\"")
                            return
                        
                        print(f"\n🔄 正在自动生成 concepts CSV 文件...")
                        try:
                            api_key = args.api_key or os.environ.get('GOOGLE_API_KEY') or os.environ.get('GEMINI_API_KEY')
                            if not api_key:
                                print(f"❌ 错误：未设置 Gemini API 密钥")
                                print(f"请设置环境变量 GEMINI_API_KEY 或 GOOGLE_API_KEY，或使用 --api-key 参数")
                                return
                            
                            # 直接使用已找到的 bookId，避免重复查找
                            generate_concepts(book_id=book_id, api_key=api_key, fetch_data=args.fetch_data)
                            
                            # 重新检查文件
                            if target_file.exists():
                                csv_files.append(target_file)
                                print(f"✓ 成功生成 concepts CSV 文件")
                            else:
                                print(f"⚠️  生成完成，但未找到对应的 CSV 文件")
                                return
                        except Exception as e:
                            print(f"❌ 自动生成 concepts 失败: {e}")
                            import traceback
                            traceback.print_exc()
                            return
                    else:
                        print(f"\n提示：可以使用 --auto-generate 参数自动生成：")
                        print(f"  python anki/scripts/import_concepts_to_anki.py --title \"{args.book_name}\" --auto-generate")
                        return
            else:
                print(f"⚠️  未找到书名 '{args.book_name}' 对应的 bookId")
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
    print(f"\n正在同步到 AnkiWeb...")
    if anki_client.sync():
        print(f"✓ 同步成功")
    else:
        print(f"⚠️  同步失败，请稍后手动同步")


if __name__ == "__main__":
    main()

