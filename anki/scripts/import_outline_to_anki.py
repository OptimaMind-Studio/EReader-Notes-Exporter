#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
将 outline HTML/Markdown 文件导入到 Anki
从 outline 文件中提取关键概念词表格，使用 AnkiConnect API 将笔记添加到 Anki
"""

import json
import re
import os
import sys
import csv
import requests
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from bs4 import BeautifulSoup
from config import (
    ANKI_CONNECT_URL,
    ANKI_MODEL_NAME,
    DECK_NAME_PREFIX,
    DEFAULT_TAGS,
    OUTLINE_DECK_NAME_FORMAT,
    OUTLINE_FIELD_MAPPING
)

# 导入 generate_outline 模块
try:
    # 从项目根目录运行时
    script_dir = Path(__file__).parent  # anki/scripts
    project_root = script_dir.parent.parent  # 项目根目录
    sys.path.insert(0, str(project_root))
    from llm.scripts.generate_outline import process_csv_file as generate_outline
except ImportError:
    # 如果导入失败，尝试直接导入
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent.parent / "llm" / "scripts"))
        from generate_outline import process_csv_file as generate_outline
    except ImportError:
        generate_outline = None


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
    
    def update_note_fields(self, note_id: int, fields: Dict[str, str]) -> None:
        """
        更新卡片的字段
        
        Args:
            note_id: 卡片 ID
            fields: 字段字典（字段名 -> 字段值）
        """
        self._invoke("updateNoteFields", note={
            "id": note_id,
            "fields": fields
        })
    
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
        查找重复的卡片（优先使用 Name 字段，如果没有则使用第一个字段）
        
        Args:
            deck_name: 卡牌组名称
            model_name: 卡牌模板名称
            fields: 字段字典
        
        Returns:
            重复卡片的 ID 列表
        """
        if not fields:
            return []
        
        # 优先使用 Name 字段来查找重复卡片（这是卡牌的主要标识字段）
        field_value = fields.get('Name', '')
        if not field_value:
            # 如果没有 Name 字段，使用第一个字段
            field_value = list(fields.values())[0] if fields else ""
        
        if not field_value:
            return []
        
        # 构建查询：查找相同卡牌组、相同模板、相同字段值的卡片
        # 转义特殊字符
        escaped_deck_name = deck_name.replace('"', '\\"')
        escaped_field_value = str(field_value).replace('"', '\\"')
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


def parse_html_outline(html_file: Path) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    解析 HTML outline 文件，提取书名、领域和完整的 HTML 文档
    
    Args:
        html_file: HTML 文件路径
    
    Returns:
        (书名, 领域, 完整HTML文档) 元组
        返回完整的 HTML 文档（包括 <html>、<head>、<body> 等标签），
        以确保在 Anki 中正确显示样式和格式
    """
    try:
        with open(html_file, 'r', encoding='utf-8') as f:
            html_content = f.read()
    except Exception as e:
        print(f"错误：读取 HTML 文件失败 {html_file}: {e}")
        return None, None, None
    
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # 提取书名（从 <h1> 标签，格式："{书名} - 学习大纲"）
    book_title = None
    h1_tags = soup.find_all('h1')
    for h1 in h1_tags:
        text = h1.get_text().strip()
        if '学习大纲' in text or 'outline' in text.lower():
            # 提取书名（去除 " - 学习大纲" 后缀）
            book_title = re.sub(r'\s*[-–—]\s*学习大纲.*$', '', text, flags=re.IGNORECASE).strip()
            if book_title:
                break
    
    # 提取领域（从 <p><strong>领域</strong>: {领域}</p>）
    domain = None
    p_tags = soup.find_all('p')
    for p in p_tags:
        text = p.get_text().strip()
        if '领域' in text or 'domain' in text.lower():
            # 提取领域值
            match = re.search(r'领域[：:]\s*(.+)', text)
            if not match:
                match = re.search(r'domain[：:]\s*(.+)', text, re.IGNORECASE)
            if match:
                domain = match.group(1).strip()
                break
    
    # 返回完整的 HTML 文档（保留完整的 HTML 结构，包括 html、head、body 标签）
    # 这样可以保留样式、meta 信息等，确保在 Anki 中正确显示
    return book_title, domain, html_content


def markdown_to_html(md_content: str) -> str:
    """
    将 Markdown 内容转换为 HTML
    
    Args:
        md_content: Markdown 内容
    
    Returns:
        HTML 内容
    """
    # 简单的 Markdown 到 HTML 转换
    html = md_content
    
    # 转换标题 (# -> <h1>, ## -> <h2>, 等等)
    for i in range(6, 0, -1):  # 从 h6 到 h1
        pattern = r'^' + ('#' * i) + r'\s+(.+)$'
        replacement = f'<h{i}>\\1</h{i}>'
        html = re.sub(pattern, replacement, html, flags=re.MULTILINE)
    
    # 转换加粗 (**text** -> <strong>text</strong>)
    html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
    
    # 转换斜体 (*text* -> <em>text</em>)
    html = re.sub(r'(?<!\*)\*([^*]+?)\*(?!\*)', r'<em>\1</em>', html)
    
    # 转换代码块 (```code``` -> <pre><code>code</code></pre>)
    html = re.sub(r'```([^`]+)```', r'<pre><code>\1</code></pre>', html, flags=re.DOTALL)
    
    # 转换行内代码 (`code` -> <code>code</code>)
    html = re.sub(r'`([^`]+)`', r'<code>\1</code>', html)
    
    # 转换水平线 (--- -> <hr>)
    html = re.sub(r'^---\s*$', r'<hr>', html, flags=re.MULTILINE)
    
    # 转换无序列表 (- item -> <li>item</li>)
    lines = html.split('\n')
    in_list = False
    result_lines = []
    for line in lines:
        # 检查是否是列表项
        list_match = re.match(r'^(\s*)[-*+]\s+(.+)$', line)
        if list_match:
            indent = len(list_match.group(1))
            content = list_match.group(2)
            if not in_list:
                result_lines.append('<ul>')
                in_list = True
            result_lines.append(f'{"  " * indent}<li>{content}</li>')
        else:
            if in_list:
                result_lines.append('</ul>')
                in_list = False
            result_lines.append(line)
    if in_list:
        result_lines.append('</ul>')
    html = '\n'.join(result_lines)
    
    # 转换段落（空行分隔的段落 -> <p>...</p>）
    paragraphs = re.split(r'\n\s*\n', html)
    html_paragraphs = []
    for para in paragraphs:
        para = para.strip()
        if para and not para.startswith('<') and not para.startswith('</'):
            html_paragraphs.append(f'<p>{para}</p>')
        else:
            html_paragraphs.append(para)
    html = '\n'.join(html_paragraphs)
    
    # 包装成完整的 HTML 文档
    html = f'<html><head><meta charset="utf-8"></head><body>\n{html}\n</body></html>'
    
    return html


def parse_markdown_outline(md_file: Path) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    解析 Markdown outline 文件，提取书名、领域，并将 Markdown 转换为 HTML
    
    Args:
        md_file: Markdown 文件路径
    
    Returns:
        (书名, 领域, HTML内容) 元组
    """
    try:
        with open(md_file, 'r', encoding='utf-8') as f:
            md_content = f.read()
    except Exception as e:
        print(f"错误：读取 Markdown 文件失败 {md_file}: {e}")
        return None, None, None
    
    # 提取书名（从第一行的标题，格式："{书名} - 学习大纲"）
    book_title = None
    lines = md_content.split('\n')
    for line in lines[:10]:  # 只检查前10行
        if '学习大纲' in line or 'outline' in line.lower():
            # 提取书名（去除 " - 学习大纲" 后缀）
            book_title = re.sub(r'^#+\s*', '', line)  # 去除 markdown 标题标记
            book_title = re.sub(r'\s*[-–—]\s*学习大纲.*$', '', book_title, flags=re.IGNORECASE).strip()
            if book_title:
                break
    
    # 提取领域（从 "**领域**: {领域}" 格式）
    domain = None
    for line in lines[:20]:  # 只检查前20行
        if '领域' in line or 'domain' in line.lower():
            match = re.search(r'领域[：:]\s*(.+)', line)
            if not match:
                match = re.search(r'domain[：:]\s*(.+)', line, re.IGNORECASE)
            if match:
                domain = match.group(1).strip()
                # 去除可能的 markdown 格式标记
                domain = re.sub(r'\*\*', '', domain)
                break
    
    # 将 Markdown 转换为 HTML
    html_content = markdown_to_html(md_content)
    
    return book_title, domain, html_content


def map_outline_fields_to_anki_fields(concept_data: Dict[str, str], book_title: str, domain: str, field_mapping: Dict[str, str]) -> Dict[str, str]:
    """
    将 outline 概念数据映射到 Anki 字段
    
    Args:
        concept_data: 概念数据字典（包含 concept, block_number, category, explanation）
        book_title: 书名
        domain: 领域
        field_mapping: 字段映射关系（outline 字段名 -> Anki 字段名）
    
    Returns:
        Anki 字段字典
    """
    anki_fields = {}
    
    # 映射各个字段
    for outline_field, anki_field in field_mapping.items():
        if outline_field == 'concept':
            anki_fields[anki_field] = concept_data.get('concept', '')
        elif outline_field == 'source':
            anki_fields[anki_field] = book_title
        elif outline_field == 'domain':
            anki_fields[anki_field] = domain
        elif outline_field == 'category':
            anki_fields[anki_field] = concept_data.get('category', '')
        elif outline_field == 'explanation':
            # 解释字段可能需要 HTML 格式处理
            explanation = concept_data.get('explanation', '')
            anki_fields[anki_field] = explanation.strip()
        elif outline_field == 'block_number':
            anki_fields[anki_field] = concept_data.get('block_number', '')
        else:
            anki_fields[anki_field] = ""
    
    return anki_fields


def import_outline_to_anki(outline_file: Path, anki_client: AnkiConnectClient, model_name: Optional[str] = None, 
                          field_mapping: Optional[Dict[str, str]] = None, dry_run: bool = False, sync: bool = False):
    """
    将 outline 文件导入到 Anki
    
    Args:
        outline_file: outline 文件路径（HTML 或 Markdown）
        anki_client: AnkiConnect 客户端
        model_name: Anki 卡牌模板名称（默认: KWDict）
        field_mapping: 字段映射关系（如果为 None，使用默认映射）
        dry_run: 是否为试运行（不实际添加卡片）
        sync: 是否同步到 AnkiWeb
    """
    if field_mapping is None:
        field_mapping = OUTLINE_FIELD_MAPPING
    
    if model_name is None:
        model_name = ANKI_MODEL_NAME
    
    print(f"\n{'='*60}")
    print(f"处理文件: {outline_file.name}")
    print(f"{'='*60}")
    
    # 根据文件扩展名选择解析方法
    if outline_file.suffix.lower() == '.html':
        book_title, domain, outline_content = parse_html_outline(outline_file)
    elif outline_file.suffix.lower() == '.md':
        book_title, domain, outline_content = parse_markdown_outline(outline_file)
    else:
        print(f"⚠️  不支持的文件格式: {outline_file.suffix}")
        return
    
    if not book_title:
        print(f"⚠️  无法获取书名，跳过")
        return
    
    if not outline_content:
        print(f"⚠️  无法读取 outline 内容，跳过")
        return
    
    print(f"书名: {book_title}")
    if domain:
        print(f"领域: {domain}")
    
    # 构建卡牌组名称（使用配置中的格式）
    deck_name = OUTLINE_DECK_NAME_FORMAT.format(book_title=book_title)
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
    
    # 准备要添加的卡片（只有一张，包含整个 outline）
    print(f"\n检查重复卡片...")
    
    # 构建卡片字段
    anki_fields = {
        'Name': f"{book_title} - 学习大纲",
        'Source': book_title,
        'Field': domain or "",
        'Taxonomy': '学习大纲',
        'AINotes': outline_content,
        'References': ''
    }
    
    # 检查是否已存在重复卡片（基于 Name 字段）
    duplicate_notes = anki_client.find_duplicate_notes(deck_name, model_name, anki_fields)
    
    if dry_run:
        print("🔍 试运行模式：不会实际添加或更新卡片")
        if duplicate_notes:
            print(f"检测到已存在的卡片（ID: {duplicate_notes[0]}），将更新内容")
        else:
            print(f"将创建新卡片")
        print(f"卡片内容:")
        print(json.dumps({
            "deckName": deck_name,
            "modelName": model_name,
            "fields": anki_fields,
            "tags": DEFAULT_TAGS + ["outline"]
        }, ensure_ascii=False, indent=2))
        # 注意：同步操作延迟到所有文件处理完成后统一执行
        return
    
    if duplicate_notes:
        # 如果已存在，更新卡片内容
        note_id = duplicate_notes[0]
        print(f"\n检测到已存在的学习大纲卡片（ID: {note_id}），正在更新内容...")
        try:
            anki_client.update_note_fields(note_id, anki_fields)
            print(f"✓ 成功更新学习大纲卡片")
        except Exception as e:
            print(f"❌ 更新卡片失败: {e}")
    else:
        # 如果不存在，创建新卡片
        print(f"\n准备添加 1 张卡片（学习大纲）...")
        note = {
            "deckName": deck_name,
            "modelName": model_name,
            "fields": anki_fields,
            "tags": DEFAULT_TAGS + ["outline"]
        }
        
        try:
            note_id = anki_client.add_note(
                deck_name=note['deckName'],
                model_name=note['modelName'],
                fields=note['fields'],
                tags=note.get('tags', [])
            )
            if note_id:
                print(f"✓ 成功添加学习大纲卡片到 Anki")
            else:
                print(f"⚠️  添加卡片失败")
        except Exception as e:
            error_msg = str(e)
            if 'duplicate' in error_msg.lower():
                # 如果是重复错误，尝试更新而不是跳过
                print(f"⚠️  卡片已存在（重复），尝试更新...")
                try:
                    # 重新查找重复的卡片
                    duplicate_notes = anki_client.find_duplicate_notes(deck_name, model_name, anki_fields)
                    if duplicate_notes:
                        note_id = duplicate_notes[0]
                        anki_client.update_note_fields(note_id, anki_fields)
                        print(f"✓ 成功更新学习大纲卡片（ID: {note_id}）")
                    else:
                        print(f"⚠️  无法找到重复卡片，跳过")
                except Exception as update_error:
                    print(f"⚠️  更新卡片失败: {update_error}，跳过")
            else:
                print(f"❌ 添加卡片失败: {e}")
    
    # 注意：同步操作延迟到所有文件处理完成后统一执行
    # 如果需要同步到 AnkiWeb，会在 main 函数中统一处理
    
    # 处理每个 block 的卡牌
    # 从文件名中提取 book_id（格式：{book_id}_outline.html 或 {book_id}_outline.md）
    book_id = None
    if outline_file:
        file_stem = outline_file.stem  # 例如：38894783_outline
        # 提取 book_id（文件名前缀，在 _outline 之前）
        if '_outline' in file_stem:
            book_id = file_stem.split('_outline')[0]
        elif '_' in file_stem:
            # 如果没有 _outline，尝试提取第一个下划线前的部分
            book_id = file_stem.split('_')[0]
    
    if book_id:
        print(f"\n处理 block 卡牌...")
        import_block_cards_to_anki(
            book_id=book_id,
            book_title=book_title,
            domain=domain,
            anki_client=anki_client,
            model_name=model_name,
            deck_name=deck_name,
            field_mapping=field_mapping,
            dry_run=dry_run,
            project_root=outline_file.parent.parent.parent.parent if outline_file else None
        )
    else:
        print(f"\n⚠️  无法从文件名提取 book_id，跳过 block 卡牌导入")


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


def import_block_cards_to_anki(book_id: str, book_title: str, domain: Optional[str], 
                                anki_client: AnkiConnectClient, model_name: str, 
                                deck_name: str, field_mapping: Dict[str, str],
                                dry_run: bool = False, project_root: Optional[Path] = None):
    """
    从 outline_blocks.csv 文件中读取每个 block，并为每个 block 创建一张卡牌
    
    Args:
        book_id: 书籍ID
        book_title: 书名
        domain: 领域
        anki_client: AnkiConnect 客户端
        model_name: Anki 卡牌模板名称
        deck_name: 卡牌组名称
        field_mapping: 字段映射关系
        dry_run: 是否为试运行
        project_root: 项目根目录
    """
    if project_root is None:
        # 尝试从当前文件位置推断项目根目录
        script_dir = Path(__file__).parent  # anki/scripts
        project_root = script_dir.parent.parent  # 项目根目录
    
    # 查找 outline_blocks.csv 文件
    outline_dir = project_root / "llm" / "output" / "outlines"
    blocks_csv_file = outline_dir / f"{book_id}_outline_blocks.csv"
    
    if not blocks_csv_file.exists():
        print(f"  ⚠️  未找到 block CSV 文件: {blocks_csv_file}")
        print(f"     跳过 block 卡牌导入")
        return
    
    # 读取章节名称映射
    chapter_mapping = get_chapter_name_mapping(book_id, project_root)
    
    # 读取 blocks CSV 文件
    blocks = []
    try:
        with open(blocks_csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                blocks.append(row)
        print(f"  读取到 {len(blocks)} 个 block")
    except Exception as e:
        print(f"  ❌ 读取 block CSV 文件失败: {e}")
        return
    
    if not blocks:
        print(f"  ⚠️  block CSV 文件为空")
        return
    
    # 准备要添加的卡片
    notes_to_add = []
    skipped_count = 0
    
    print(f"\n检查重复卡片...")
    for block in blocks:
        start_chapter = block.get('start_chapter', '').strip()
        start_chapter_name = chapter_mapping.get(int(start_chapter), f'章节{start_chapter}') if start_chapter.isdigit() else f'章节{start_chapter}'
        html_content = block.get('html', '').strip()
        
        if not html_content:
            skipped_count += 1
            continue
        
        # 构建卡片名称：书名-学习大纲-开始章节号-开始章节名
        card_name = f"{book_title}-学习大纲-{start_chapter}-{start_chapter_name}"
        
        # 构建卡片字段
        anki_fields = {
            'Name': card_name,
            'Source': book_title,
            'Field': domain or "",
            'Taxonomy': '学习大纲',
            'AINotes': html_content,
            'References': ''
        }
        
        # 检查是否已存在重复卡片（基于 Name 字段）
        duplicate_notes = anki_client.find_duplicate_notes(deck_name, model_name, anki_fields)
        if duplicate_notes:
            skipped_count += 1
            continue
        
        # 构建卡片数据
        note = {
            "deckName": deck_name,
            "modelName": model_name,
            "fields": anki_fields,
            "tags": DEFAULT_TAGS + ["outline", "block"]
        }
        
        notes_to_add.append(note)
    
    if skipped_count > 0:
        print(f"跳过 {skipped_count} 条记录（缺少内容或已存在的重复卡片）")
    
    if not notes_to_add:
        print("没有有效的 block 记录需要添加")
        return
    
    print(f"\n准备添加 {len(notes_to_add)} 张 block 卡片...")
    
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
    batch_size = 10
    added_count = 0
    failed_count = 0
    duplicate_count = 0
    
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
                            duplicate_count += 1
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
                        duplicate_count += 1
                    else:
                        failed_count += 1
    
    print(f"\n✓ 完成！共添加 {added_count}/{len(notes_to_add)} 张 block 卡片到 Anki")
    if duplicate_count > 0:
        print(f"⚠️  跳过 {duplicate_count} 张卡片（可能是重复卡片）")
    if failed_count > 0:
        print(f"❌ 失败 {failed_count} 张卡片")


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
    import csv
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
        description='将 outline HTML/Markdown 文件导入到 Anki',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  # 导入所有 outline 文件
  python import_outline_to_anki.py
  
  # 导入指定的 HTML 文件
  python import_outline_to_anki.py --file llm/output/outlines/3300089819_outline.html
  
  # 导入指定的 Markdown 文件
  python import_outline_to_anki.py --file llm/output/outlines/3300089819_outline.md
  
  # 根据 bookId 过滤
  python import_outline_to_anki.py --book-id 3300089819
  
  # 根据书名过滤
  python import_outline_to_anki.py --title "极简央行课"
  
  # 自动生成 outline 文件（如果不存在）
  python import_outline_to_anki.py --title "极简央行课" --auto-generate
  
  # 先重新 fetch 数据，再自动生成 outline
  python import_outline_to_anki.py --title "极简央行课" --auto-generate --fetch
  
  # 自动生成并指定 API key
  python import_outline_to_anki.py --title "极简央行课" --auto-generate --api-key YOUR_API_KEY
  
  # 试运行（不实际添加卡片）
  python import_outline_to_anki.py --dry-run
  
  # 指定 AnkiConnect 地址
  python import_outline_to_anki.py --anki-url http://127.0.0.1:8765
  
  # 导入后自动同步到 AnkiWeb
  python import_outline_to_anki.py --sync
        """
    )
    
    parser.add_argument('--file', '--outline-file', dest='outline_file', type=str, default=None,
                       help='要导入的 outline 文件路径（可选，如果不指定则导入所有 outline 文件）')
    
    # 书籍过滤参数（互斥）
    book_group = parser.add_mutually_exclusive_group()
    book_group.add_argument('--book-id', '--id', dest='book_id', type=str, default=None,
                           help='书籍ID（可选，如果提供则只导入该书籍的 outline 文件）')
    book_group.add_argument('--title', '--book-title', '--book-name', dest='book_name', type=str, default=None,
                           help='书籍名称（可选，如果提供则只导入该书籍的 outline 文件）')
    
    parser.add_argument('--anki-url', dest='anki_url', type=str, default=None,
                       help=f'AnkiConnect API 地址（默认: {ANKI_CONNECT_URL}）')
    parser.add_argument('--model', '--model-name', dest='model_name', type=str, default=None,
                       help=f'Anki 卡牌模板名称（默认: {ANKI_MODEL_NAME}）')
    parser.add_argument('--dry-run', dest='dry_run', action='store_true',
                       help='试运行模式，不实际添加卡片')
    parser.add_argument('--sync', dest='sync', action='store_true',
                       help='导入完成后同步到 AnkiWeb（已弃用：现在总是会自动同步）')
    parser.add_argument('--auto-generate', dest='auto_generate', action='store_true',
                       help='如果找不到 outline 文件，自动调用 generate_outline.py 生成')
    parser.add_argument('--fetch', '--refresh-data', dest='fetch_data', action='store_true',
                       help='在生成 outline 之前，先重新 fetch 笔记数据（需要 --auto-generate）')
    parser.add_argument('--api-key', dest='api_key', type=str, default=None,
                       help='Gemini API 密钥（用于自动生成 outline，优先从环境变量 GEMINI_API_KEY 或 GOOGLE_API_KEY 读取）')
    
    args = parser.parse_args()
    
    # 如果指定了 --fetch 但没有 --auto-generate，提示用户
    if args.fetch_data and not args.auto_generate:
        print("⚠️  警告：--fetch 参数需要配合 --auto-generate 使用")
        print("   将自动启用 --auto-generate")
        args.auto_generate = True
    
    # 获取脚本所在目录
    script_dir = Path(__file__).parent  # anki/scripts
    project_root = script_dir.parent.parent  # 项目根目录
    
    # 默认 outline 目录
    outline_dir = project_root / "llm" / "output" / "outlines"
    
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
    outline_files = []
    target_book_id = None
    
    if args.outline_file:
        # 如果指定了文件，只处理该文件
        outline_file = Path(args.outline_file)
        if not outline_file.is_absolute():
            outline_file = project_root / outline_file
        if outline_file.exists():
            outline_files = [outline_file]
        else:
            print(f"❌ 错误：文件不存在: {outline_file}")
            return
    else:
        # 否则处理所有 outline 文件
        if not outline_dir.exists():
            print(f"❌ 错误：目录不存在: {outline_dir}")
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
        
        # 获取所有 outline 文件（HTML 和 Markdown）
        all_html_files = list(outline_dir.glob("*.html"))
        all_md_files = list(outline_dir.glob("*.md"))
        
        if target_book_id:
            # 根据 bookId 过滤文件（文件名格式：{bookId}_outline.html 或 {bookId}_outline.md）
            # 优先选择 HTML 文件，如果不存在 HTML 文件才选择 Markdown 文件
            html_files_for_book = [f for f in all_html_files if f.stem.startswith(f"{target_book_id}_")]
            md_files_for_book = [f for f in all_md_files if f.stem.startswith(f"{target_book_id}_")]
            
            if html_files_for_book:
                outline_files = html_files_for_book
            else:
                outline_files = md_files_for_book
            
            # 如果指定了 --fetch，即使找到了文件，也要先 fetch 并重新生成
            if args.fetch_data:
                print(f"\n🔄 检测到 --fetch 参数，将先重新 fetch 数据并生成 outline...")
                if generate_outline is None:
                    print(f"\n❌ 错误：无法导入 generate_outline 模块，无法重新生成 outline")
                    print(f"请手动运行以下命令重新生成 outline：")
                    if args.book_name:
                        print(f"  python llm/scripts/generate_outline.py --title \"{args.book_name}\" --fetch")
                    else:
                        print(f"  python llm/scripts/generate_outline.py --book-id {target_book_id} --fetch")
                    return
                
                print(f"\n🔄 正在重新生成 outline 文件（使用最新数据）...")
                try:
                    # 获取 API key
                    api_key = args.api_key or os.environ.get('GOOGLE_API_KEY') or os.environ.get('GEMINI_API_KEY')
                    if not api_key:
                        print(f"❌ 错误：未设置 Gemini API 密钥")
                        print(f"请设置环境变量 GEMINI_API_KEY 或 GOOGLE_API_KEY，或使用 --api-key 参数")
                        return
                    
                    # 调用生成函数（优先使用 bookId，因为已经找到了）
                    # 传递 fetch_data=True，先重新 fetch 数据
                    generate_outline(book_id=target_book_id, api_key=api_key, fetch_data=True)
                    
                    # 重新检查文件（优先选择 HTML 文件）
                    all_html_files = list(outline_dir.glob("*.html"))
                    all_md_files = list(outline_dir.glob("*.md"))
                    html_files_for_book = [f for f in all_html_files if f.stem.startswith(f"{target_book_id}_")]
                    md_files_for_book = [f for f in all_md_files if f.stem.startswith(f"{target_book_id}_")]
                    if html_files_for_book:
                        outline_files = html_files_for_book
                    else:
                        outline_files = md_files_for_book
                    
                    if outline_files:
                        print(f"✓ 成功重新生成 outline 文件")
                    else:
                        print(f"⚠️  生成完成，但未找到对应的 outline 文件")
                        return
                except Exception as e:
                    print(f"❌ 重新生成 outline 失败: {e}")
                    import traceback
                    traceback.print_exc()
                    print(f"\n请手动运行以下命令重新生成 outline：")
                    if args.book_name:
                        print(f"  python llm/scripts/generate_outline.py --title \"{args.book_name}\" --fetch")
                    else:
                        print(f"  python llm/scripts/generate_outline.py --book-id {target_book_id} --fetch")
                    return
            
            elif not outline_files:
                print(f"⚠️  未找到 bookId '{target_book_id}' 对应的 outline 文件")
                
                # 如果启用了自动生成，尝试自动生成 outline
                if args.auto_generate:
                    if generate_outline is None:
                        print(f"\n❌ 错误：无法导入 generate_outline 模块，无法自动生成 outline")
                        print(f"请手动运行以下命令生成 outline：")
                        if args.book_name:
                            print(f"  python llm/scripts/generate_outline.py --title \"{args.book_name}\"")
                        else:
                            print(f"  python llm/scripts/generate_outline.py --book-id {target_book_id}")
                        return
                    
                    print(f"\n🔄 正在自动生成 outline 文件...")
                    try:
                        # 获取 API key
                        api_key = args.api_key or os.environ.get('GOOGLE_API_KEY') or os.environ.get('GEMINI_API_KEY')
                        if not api_key:
                            print(f"❌ 错误：未设置 Gemini API 密钥")
                            print(f"请设置环境变量 GEMINI_API_KEY 或 GOOGLE_API_KEY，或使用 --api-key 参数")
                            return
                        
                        # 调用生成函数（优先使用 bookId，因为已经找到了）
                        # 传递 fetch_data 参数，如果用户指定了 --fetch，则先重新 fetch 数据
                        generate_outline(book_id=target_book_id, api_key=api_key, fetch_data=args.fetch_data)
                        
                        # 重新检查文件（优先选择 HTML 文件）
                        all_html_files = list(outline_dir.glob("*.html"))
                        all_md_files = list(outline_dir.glob("*.md"))
                        html_files_for_book = [f for f in all_html_files if f.stem.startswith(f"{target_book_id}_")]
                        md_files_for_book = [f for f in all_md_files if f.stem.startswith(f"{target_book_id}_")]
                        if html_files_for_book:
                            outline_files = html_files_for_book
                        else:
                            outline_files = md_files_for_book
                        
                        if outline_files:
                            print(f"✓ 成功生成 outline 文件")
                        else:
                            print(f"⚠️  生成完成，但未找到对应的 outline 文件")
                            return
                    except Exception as e:
                        print(f"❌ 自动生成 outline 失败: {e}")
                        import traceback
                        traceback.print_exc()
                        print(f"\n请手动运行以下命令生成 outline：")
                        if args.book_name:
                            print(f"  python llm/scripts/generate_outline.py --title \"{args.book_name}\"")
                        else:
                            print(f"  python llm/scripts/generate_outline.py --book-id {target_book_id}")
                        return
                else:
                    print(f"\n提示：请先生成 outline 文件，可以使用以下命令：")
                    if args.book_name:
                        print(f"  python llm/scripts/generate_outline.py --title \"{args.book_name}\"")
                    else:
                        print(f"  python llm/scripts/generate_outline.py --book-id {target_book_id}")
                    print(f"\n或者使用 --auto-generate 参数自动生成：")
                    if args.book_name:
                        print(f"  python anki/scripts/import_outline_to_anki.py --title \"{args.book_name}\" --auto-generate")
                    else:
                        print(f"  python anki/scripts/import_outline_to_anki.py --book-id {target_book_id} --auto-generate")
                    print(f"\n或者查看目录中的所有 outline 文件：")
                    print(f"  ls -la {outline_dir}")
                    return
            print(f"找到 {len(outline_files)} 个匹配的 outline 文件（bookId: {target_book_id}）")
        else:
            # 优先选择 HTML 文件，如果不存在 HTML 文件才选择 Markdown 文件
            if all_html_files:
                outline_files = all_html_files
            else:
                outline_files = all_md_files
            if not outline_files:
                print(f"⚠️  未找到 outline 文件: {outline_dir}")
                return
            print(f"找到 {len(outline_files)} 个 outline 文件（优先选择 HTML 格式）")
    
    # 依次处理每个 outline 文件
    for outline_file in outline_files:
        try:
            import_outline_to_anki(
                outline_file=outline_file,
                anki_client=anki_client,
                model_name=args.model_name or ANKI_MODEL_NAME,
                field_mapping=OUTLINE_FIELD_MAPPING,
                dry_run=args.dry_run,
                sync=args.sync
            )
        except Exception as e:
            print(f"❌ 处理文件 {outline_file.name} 时出错: {e}")
            import traceback
            traceback.print_exc()
    
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
