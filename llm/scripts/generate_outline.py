#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
学习大纲生成工具
从笔记 CSV 文件中按章节分组，使用 Gemini API 生成学习大纲
"""

import sys
import os
import csv
import json
import time
import re
import html
import argparse
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Tuple
from collections import defaultdict
from google import genai

# 导入 prompt 模板
try:
    # 从项目根目录运行时
    from llm.prompts import OUTLINE_PROMPT_TEMPLATE
except ImportError:
    # 从 llm 目录运行时
    from prompts import OUTLINE_PROMPT_TEMPLATE


class OutlineGenerator:
    """使用 Gemini API 生成学习大纲"""
    
    PROMPT_TEMPLATE = OUTLINE_PROMPT_TEMPLATE
    
    def __init__(self, api_key: Optional[str] = None, role: str = "学习者"):
        """
        初始化 Gemini API 客户端
        
        Args:
            api_key: Gemini API 密钥，如果为 None 则从环境变量读取
            role: 角色（默认为"学习者"）
        """
        if api_key is None:
            api_key = os.environ.get('GOOGLE_API_KEY') or os.environ.get('GEMINI_API_KEY')
        
        if not api_key:
            raise ValueError(
                "请提供 Gemini API 密钥。可以通过以下方式：\n"
                "1. 作为参数传入：OutlineGenerator(api_key='your_key')\n"
                "2. 设置环境变量：export GEMINI_API_KEY='your_api_key' 或 export GOOGLE_API_KEY='your_api_key'"
            )
        
        self.client = genai.Client(api_key=api_key)
        self.role = role
    
    def _clean_json_string(self, json_str: str) -> str:
        """
        清理 JSON 字符串中的控制字符
        
        Args:
            json_str: 原始 JSON 字符串
        
        Returns:
            清理后的 JSON 字符串
        """
        # 移除字符串值外的控制字符（\x00-\x1F，除了 \n, \r, \t）
        # 这是一个复杂的问题，因为我们需要区分字符串值内外的控制字符
        
        # 简单方法：尝试修复常见的控制字符问题
        # 移除字符串值外的控制字符
        lines = json_str.split('\n')
        cleaned_lines = []
        in_string = False
        escape_next = False
        
        for line in lines:
            cleaned_line = []
            for char in line:
                if escape_next:
                    cleaned_line.append(char)
                    escape_next = False
                    continue
                
                if char == '\\':
                    escape_next = True
                    cleaned_line.append(char)
                    continue
                
                if char == '"' and not escape_next:
                    in_string = not in_string
                    cleaned_line.append(char)
                    continue
                
                # 如果是控制字符且不在字符串值中，跳过
                if not in_string and ord(char) < 32 and char not in ['\n', '\r', '\t']:
                    continue
                
                cleaned_line.append(char)
            
            cleaned_lines.append(''.join(cleaned_line))
        
        return '\n'.join(cleaned_lines)
    
    def generate_outline(self, mark_notes: str, review_notes: str, max_retries: int = 3) -> Dict[str, str]:
        """
        生成学习大纲
        
        Args:
            mark_notes: 划线笔记（包含章节标题和划线文本）
            review_notes: 点评笔记
            max_retries: 最大重试次数（当 HTML 解析失败时）
        
        Returns:
            包含 'markdown' 和 'html' 的字典
        """
        # 替换 prompt 模板中的占位符
        prompt = self.PROMPT_TEMPLATE.replace("{{划线笔记}}", mark_notes)
        prompt = prompt.replace("{{点评笔记}}", review_notes)
        
        last_error = None
        last_response_text = None
        
        for attempt in range(max_retries):
            try:
                # 如果不是第一次尝试，打印重试信息
                if attempt > 0:
                    print(f"  🔄 重试第 {attempt} 次...")
                
                response = self.client.models.generate_content(
                    model='gemini-2.0-flash-001',
                    contents=prompt,
                )
                
                # 获取响应文本
                if hasattr(response, 'text'):
                    response_text = response.text
                elif hasattr(response, 'candidates') and len(response.candidates) > 0:
                    response_text = response.candidates[0].content.parts[0].text
                else:
                    response_text = str(response)
                
                response_text = response_text.strip()
                last_response_text = response_text
                
                # 清理响应文本，提取 HTML 部分
                # 移除可能的 markdown 代码块标记（包括 ```html, ```, 等）
                if response_text.startswith('```'):
                    lines = response_text.split('\n')
                    start_idx = 1
                    end_idx = len(lines)
                    for i, line in enumerate(lines):
                        if line.strip().startswith('```') and i > 0:
                            end_idx = i
                            break
                    response_text = '\n'.join(lines[start_idx:end_idx])
                
                # 移除所有剩余的 markdown 代码块标记
                response_text = re.sub(r'^```[a-z]*\n?', '', response_text, flags=re.MULTILINE)
                response_text = re.sub(r'\n?```$', '', response_text, flags=re.MULTILINE)
                response_text = response_text.strip()
                
                # 移除前后引号（如果存在）
                if response_text.startswith('"') and response_text.endswith('"'):
                    response_text = response_text[1:-1]
                if response_text.startswith("'") and response_text.endswith("'"):
                    response_text = response_text[1:-1]
                response_text = response_text.strip()
                
                # 验证和清理 HTML
                html_content = self._validate_and_clean_html(response_text)
                
                if html_content:
                    # 从 HTML 生成 markdown（简化版本）
                    markdown_content = self._html_to_markdown(html_content)
                    
                    return {
                        'markdown': markdown_content,
                        'html': html_content
                    }
                else:
                    # HTML 验证失败，重试
                    if attempt < max_retries - 1:
                        last_error = "HTML 格式验证失败"
                        print(f"  ⚠️  HTML 格式验证失败，重试...")
                        time.sleep(1)
                        continue
                    else:
                        # 如果重试次数用完，返回错误信息
                        error_text = response_text[:1000]
                        error_text = html.escape(error_text)
                        error_text = re.sub(r'```[a-z]*\n?', '', error_text)
                        error_text = re.sub(r'\n?```', '', error_text)
                        
                        return {
                            'markdown': f"HTML 格式验证失败\n\n原始响应：\n{response_text[:1000]}",
                            'html': f"<html><body><p>HTML 格式验证失败</p><pre>{error_text}</pre></body></html>"
                        }
            
            except Exception as e:
                last_error = str(e)
                error_msg = f"生成大纲时出错：{str(e)}"
                print(f"  ⚠️  {error_msg}")
                
                # 如果是网络错误或其他可重试的错误，且还有重试机会，继续重试
                if attempt < max_retries - 1:
                    time.sleep(1)  # 等待 1 秒后重试
                    continue
                
                # 如果重试次数用完，返回错误信息
                error_text = last_response_text[:1000] if last_response_text else '无响应'
                error_text = html.escape(error_text)
                error_text = re.sub(r'```[a-z]*\n?', '', error_text)
                error_text = re.sub(r'\n?```', '', error_text)
                
                return {
                    'markdown': error_msg,
                    'html': f"<html><body><p>{error_msg}</p><pre>{error_text}</pre></body></html>"
                }
        
        # 如果所有重试都失败，返回最后的错误信息
        error_text = last_response_text[:1000] if last_response_text else '无响应'
        error_text = html.escape(error_text)
        error_text = re.sub(r'```[a-z]*\n?', '', error_text)
        error_text = re.sub(r'\n?```', '', error_text)
        
        return {
            'markdown': f"生成大纲失败（已重试 {max_retries} 次）：{last_error}\n\n原始响应：\n{last_response_text[:1000] if last_response_text else '无响应'}",
            'html': f"<html><body><p>生成大纲失败（已重试 {max_retries} 次）：{last_error}</p><pre>{error_text}</pre></body></html>"
        }
    
    def _validate_and_clean_html(self, html_text: str) -> Optional[str]:
        """
        验证和清理 HTML 文本
        
        Args:
            html_text: 原始 HTML 文本
        
        Returns:
            清理后的 HTML 文本，如果无效则返回 None
        """
        if not html_text or not html_text.strip():
            return None
        
        # 检查是否包含基本的 HTML 标签
        if not re.search(r'<[hH][1-6]', html_text) and not re.search(r'<[pP]', html_text):
            # 如果没有 HTML 标签，可能不是 HTML 格式
            print(f"  ⚠️  响应中未找到 HTML 标签")
            return None
        
        # 清理控制字符（但保留字符串值中的合法转义字符）
        # 移除字符串值外的控制字符
        cleaned_html = self._clean_html_string(html_text)
        
        # 确保 HTML 是完整的（如果没有 html/body 标签，添加它们）
        if not re.search(r'<html', cleaned_html, re.IGNORECASE):
            # 如果没有完整的 HTML 结构，只返回内容部分
            # 调用者会负责包装
            return cleaned_html
        
        return cleaned_html
    
    def _clean_html_string(self, html_str: str) -> str:
        """
        清理 HTML 字符串中的控制字符
        
        Args:
            html_str: 原始 HTML 字符串
        
        Returns:
            清理后的 HTML 字符串
        """
        # 移除控制字符（除了 \n, \r, \t）
        result = []
        for char in html_str:
            if ord(char) < 32 and char not in ['\n', '\r', '\t']:
                continue
            result.append(char)
        
        return ''.join(result)
    
    def _html_to_markdown(self, html_content: str) -> str:
        """
        从 HTML 生成简化的 Markdown（用于兼容性）
        
        Args:
            html_content: HTML 内容
        
        Returns:
            Markdown 格式的文本
        """
        # 简单的 HTML 到 Markdown 转换
        # 移除 HTML 标签，保留文本内容
        markdown = html_content
        
        # 替换标题标签 - 使用 lambda 函数来处理反向引用
        def replace_header(match):
            level = int(match.group(1))
            text = match.group(2)
            return f'\n{"#" * level} {text}\n'
        
        markdown = re.sub(r'<h([1-6])>(.*?)</h\1>', replace_header, markdown, flags=re.IGNORECASE | re.DOTALL)
        
        # 替换段落标签
        markdown = re.sub(r'<p>(.*?)</p>', r'\1\n\n', markdown, flags=re.IGNORECASE | re.DOTALL)
        
        # 替换加粗标签
        markdown = re.sub(r'<strong>(.*?)</strong>', r'**\1**', markdown, flags=re.IGNORECASE | re.DOTALL)
        markdown = re.sub(r'<b>(.*?)</b>', r'**\1**', markdown, flags=re.IGNORECASE | re.DOTALL)
        
        # 移除其他 HTML 标签
        markdown = re.sub(r'<[^>]+>', '', markdown)
        
        # 清理多余的空行
        markdown = re.sub(r'\n{3,}', '\n\n', markdown)
        
        return markdown.strip()
    
    def close(self):
        """关闭客户端"""
        if hasattr(self, 'client'):
            try:
                self.client.close()
            except:
                pass


def read_csv_file(csv_file: str) -> List[Dict[str, str]]:
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
                # 只保留有 markText 的行
                if row.get('markText', '').strip():
                    rows.append(row)
        return rows
    except Exception as e:
        print(f"错误：读取 CSV 文件失败: {e}")
        return []


def group_by_chapters(rows: List[Dict[str, str]]) -> Dict[int, List[Dict[str, str]]]:
    """
    按章节分组
    
    Args:
        rows: CSV 数据行列表
    
    Returns:
        按 chapterUid 分组的字典
    """
    chapters = defaultdict(list)
    
    for row in rows:
        chapter_uid = row.get('chapterUid', '').strip()
        if chapter_uid:
            try:
                uid = int(chapter_uid)
                chapters[uid].append(row)
            except (ValueError, TypeError):
                continue
    
    return dict(sorted(chapters.items()))


def find_book_id_by_title(csv_file: str, book_title: str) -> Optional[str]:
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


def find_book_by_id(csv_file: str, book_id: str) -> Optional[Dict[str, str]]:
    """
    根据 bookId 在 CSV 文件中查找书籍信息
    
    Args:
        csv_file: CSV 文件路径
        book_id: 书籍ID
    
    Returns:
        书籍信息字典，如果未找到则返回 None
    """
    try:
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get('bookId', '').strip() == book_id:
                    return {
                        'bookId': book_id,
                        'title': row.get('title', '').strip(),
                        'author': row.get('author', '').strip(),
                        'categories': row.get('categories', '').strip()
                    }
        return None
    except Exception as e:
        print(f"错误：读取 CSV 文件失败: {e}")
        return None


def fetch_notes_data(book_id: Optional[str] = None, book_name: Optional[str] = None, project_root: Path = None) -> bool:
    """
    重新 fetch 笔记数据
    
    Args:
        book_id: 书籍ID（可选，如果提供则只 fetch 该书籍）
        book_name: 书名（可选，如果提供则只 fetch 该书籍，优先于 book_id）
        project_root: 项目根目录路径
    
    Returns:
        如果成功返回 True，否则返回 False
    """
    if project_root is None:
        script_dir = Path(__file__).parent  # llm/scripts
        project_root = script_dir.parent.parent  # 项目根目录
    
    fetch_script = project_root / "wereader" / "fetch.py"
    
    if not fetch_script.exists():
        print(f"⚠️  警告：fetch 脚本不存在: {fetch_script}")
        print(f"   请确保 wereader/fetch.py 文件存在")
        return False
    
    print(f"\n{'='*60}")
    print(f"正在重新 fetch 笔记数据...")
    print(f"{'='*60}")
    
    args = [sys.executable, str(fetch_script)]
    if book_name:
        args.extend(['--book-name', book_name])
        print(f"处理书籍: {book_name}")
    elif book_id:
        args.extend(['--book-id', book_id])
        print(f"处理书籍 ID: {book_id}")
    else:
        print(f"处理所有书籍")
    
    try:
        result = subprocess.run(
            args,
            cwd=str(project_root),
            check=False,
            capture_output=False  # 显示输出
        )
        if result.returncode == 0:
            print(f"✓ Fetch 完成")
            return True
        else:
            print(f"⚠️  Fetch 失败（退出码: {result.returncode}）")
            return False
    except Exception as e:
        print(f"❌ Fetch 执行出错: {e}")
        return False


def process_csv_file(book_id: Optional[str] = None, book_title: Optional[str] = None, output_file: Optional[str] = None, api_key: Optional[str] = None, role: str = "学习者", fetch_data: bool = False):
    """
    处理 CSV 文件，生成学习大纲
    
    Args:
        book_id: 书籍ID（与 book_title 二选一）
        book_title: 书名（与 book_id 二选一）
        output_file: 输出的 Markdown 文件路径，如果为 None 则自动生成
        api_key: Gemini API 密钥
        role: 角色（默认为"学习者"）
        fetch_data: 是否先重新 fetch 笔记数据（默认 False）
    """
    # 获取脚本所在目录
    script_dir = Path(__file__).parent  # llm/scripts
    project_root = script_dir.parent.parent  # 项目根目录
    
    # 如果启用了 fetch_data，先重新 fetch 笔记数据
    if fetch_data:
        # 优先使用 book_name（book_title），如果没有则使用 book_id
        if not fetch_notes_data(book_id=book_id, book_name=book_title, project_root=project_root):
            print(f"\n⚠️  警告：fetch 数据失败，将使用已有的笔记文件")
        else:
            print(f"\n✓ 数据已更新，继续生成 outline...\n")
    
    # 默认路径
    notebooks_csv = project_root / "wereader" / "output" / "fetch_notebooks_output.csv"
    notes_dir = project_root / "wereader" / "output" / "notes"
    
    # 1. 确定 bookId
    book_info = None
    
    if book_id:
        # 如果提供了 bookId，直接使用
        print(f"使用 bookId: {book_id}")
        book_info = find_book_by_id(str(notebooks_csv), book_id)
        if not book_info:
            print(f"错误：未找到 bookId '{book_id}' 对应的书籍")
            return
        book_id = book_info['bookId']
        book_title_display = book_info['title']
    elif book_title:
        # 如果提供了书名，查找对应的 bookId
        print(f"正在查找书名：{book_title}")
        book_id = find_book_id_by_title(str(notebooks_csv), book_title)
        if not book_id:
            print(f"错误：未找到书名 '{book_title}' 对应的 bookId")
            return
        book_info = find_book_by_id(str(notebooks_csv), book_id)
        book_title_display = book_title
    else:
        print("错误：必须提供 bookId 或 book_title 之一")
        return
    
    print(f"找到书籍: {book_title_display} (ID: {book_id})\n")
    
    # 2. 构建 CSV 文件路径
    csv_file = notes_dir / f"{book_id}.csv"
    
    if not csv_file.exists():
        print(f"错误：笔记文件不存在: {csv_file}")
        return
    
    # 读取 CSV 文件
    print(f"正在读取文件: {csv_file}")
    rows = read_csv_file(str(csv_file))
    
    if not rows:
        print("错误：文件中没有有效数据")
        return
    
    print(f"共读取 {len(rows)} 行数据")
    
    # 获取领域和书籍信息
    field = ''
    book_title = ''
    for row in rows:
        if not field:
            field = row.get('categories', '').strip()
        if not book_title:
            book_title = row.get('title', '').strip()
        if field and book_title:
            break
    
    if not field:
        field = "未知领域"
    if not book_title:
        book_title = "未知书籍"
    
    print(f"书籍: {book_title}")
    print(f"领域: {field}\n")
    
    # 按章节分组
    print("正在按章节分组...")
    chapters_dict = group_by_chapters(rows)
    chapter_uids = sorted(chapters_dict.keys())
    
    print(f"共 {len(chapter_uids)} 个章节: {chapter_uids}\n")
    
    # 初始化生成器
    generator = OutlineGenerator(api_key=api_key, role=role)
    
    # 按章节分组，每组至少50个笔记
    min_notes_per_group = 50
    
    print("=" * 60)
    print(f"开始处理（每组至少 {min_notes_per_group} 个笔记）")
    print("=" * 60)
    
    # 准备 CSV 缓存文件路径
    script_dir = Path(__file__).parent  # llm/scripts
    output_dir = script_dir.parent / "output" / "outlines"  # llm/output/outlines
    output_dir.mkdir(parents=True, exist_ok=True)
    cache_csv_file = output_dir / f"{book_id}_outline_blocks.csv"
    
    # 加载已有的 block 缓存
    existing_blocks = {}
    existing_blocks_info = {}  # 存储完整的 block 信息（包括 start_chapter, start_note_id 等）
    if cache_csv_file.exists():
        print(f"\n检测到已存在的 block 缓存文件: {cache_csv_file}")
        try:
            with open(cache_csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    block_id = row.get('block_id', '').strip()
                    if block_id:
                        existing_blocks[block_id] = {
                            'html': row.get('html', ''),
                            'markdown': row.get('markdown', ''),
                            'created_at': row.get('created_at', ''),
                            'updated_at': row.get('updated_at', '')
                        }
                        # 保存完整的 block 信息（从 CSV 列读取，而不是从 block_id 解析）
                        existing_blocks_info[block_id] = {
                            'start_chapter': row.get('start_chapter', '').strip(),
                            'start_note_id': row.get('start_note_id', '').strip(),
                            'end_chapter': row.get('end_chapter', '').strip(),
                            'end_note_id': row.get('end_note_id', '').strip()
                        }
            print(f"  已加载 {len(existing_blocks)} 个已有 block")
        except Exception as e:
            print(f"  ⚠️  读取 block 缓存文件失败: {e}")
    
    # 第一步：先生成所有 block 划分（确定所有要处理的 block）
    print(f"\n第一步：生成所有 block 划分...")
    all_block_definitions = []  # 所有 block 的定义（包含章节、笔记等）
    
    i = 0
    group_idx = 0
    
    while i < len(chapter_uids):
        # 收集当前组的所有章节
        group_chapters = []
        total_notes = 0
        
        # 从当前章节开始，累积到至少50个笔记
        j = i
        while j < len(chapter_uids) and total_notes < min_notes_per_group:
            chapter_uid = chapter_uids[j]
            chapter_rows = chapters_dict[chapter_uid]
            # 统计该章节的笔记数量（有 markText 的行）
            notes_count = len([row for row in chapter_rows if row.get('markText', '').strip()])
            
            group_chapters.append(chapter_uid)
            total_notes += notes_count
            j += 1
        
        if not group_chapters:
            break
        
        group_idx += 1
        
        # 收集这组章节的划线笔记和点评笔记，同时收集笔记 ID
        mark_notes_parts = []  # 划线笔记（包含章节标题和划线文本）
        review_notes_parts = []  # 点评笔记
        
        chapter_names = []
        first_note_id = None  # 第一个笔记的 ID
        last_note_id = None   # 最后一个笔记的 ID
        
        for chapter_uid in group_chapters:
            chapter_rows = chapters_dict[chapter_uid]
            chapter_name = chapter_rows[0].get('chapterName', f'章节{chapter_uid}') if chapter_rows else f'章节{chapter_uid}'
            chapter_names.append(chapter_name)
            
            # 按 createTime 排序，确保顺序
            chapter_rows_sorted = sorted(chapter_rows, key=lambda x: int(x.get('createTime', 0)) if x.get('createTime', '').strip().isdigit() else 0)
            
            # 添加章节标题（没有 bullet point）
            mark_notes_parts.append(chapter_name)
            
            # 收集划线笔记（有 bullet point）
            for row in chapter_rows_sorted:
                mark_text = row.get('markText', '').strip()
                if mark_text:
                    mark_notes_parts.append(f"- {mark_text}")
                    # 记录第一个和最后一个笔记 ID
                    note_id = row.get('noteId', '').strip() or row.get('createTime', '').strip()
                    if note_id:
                        if first_note_id is None:
                            first_note_id = note_id
                        last_note_id = note_id
                
                # 收集点评笔记
                review_content = row.get('reviewContent', '').strip()
                if review_content:
                    review_notes_parts.append("【原文】：" + mark_text + "【点评】：" + review_content)
        
        if not mark_notes_parts:
            i = j
            continue
        
        # 生成 block_id：开始章节号-开始笔记id-结束章节号-结束笔记id
        start_chapter = group_chapters[0]
        end_chapter = group_chapters[-1]
        block_id = f"{start_chapter}-{first_note_id or '0'}-{end_chapter}-{last_note_id or '0'}"
        
        # 保存 block 定义
        all_block_definitions.append({
            'group_idx': group_idx,
            'block_id': block_id,
            'start_chapter': start_chapter,
            'end_chapter': end_chapter,
            'start_note_id': first_note_id or '',
            'end_note_id': last_note_id or '',
            'group_chapters': group_chapters,
            'chapter_names': chapter_names,
            'mark_notes_parts': mark_notes_parts,
            'review_notes_parts': review_notes_parts,
            'total_notes': total_notes
        })
        
        i = j
    
    print(f"✓ 共划分了 {len(all_block_definitions)} 个 block")
    
    # 第二步：检查 CSV 中已存在的 block，确定哪些需要调用 LLM
    print(f"\n第二步：检查 CSV 中已存在的 block...")
    
    # 建立已有 block 的索引（按"开始章节号-开始笔记id"分组，用于查找覆盖情况）
    existing_blocks_by_start = {}  # key = "开始章节号-开始笔记id", value = list of blocks
    for block_id, block_data in existing_blocks.items():
        # 从 CSV 列读取章节信息（而不是从 block_id 解析，因为 start_note_id 可能包含 '-'）
        block_info = existing_blocks_info.get(block_id, {})
        start_chapter = block_info.get('start_chapter', '')
        start_note_id = block_info.get('start_note_id', '')
        end_chapter = block_info.get('end_chapter', '')
        
        start_key = f"{start_chapter}-{start_note_id}"
        if start_key not in existing_blocks_by_start:
            existing_blocks_by_start[start_key] = []
        existing_blocks_by_start[start_key].append({
            'block_id': block_id,
            'start_chapter': start_chapter,
            'start_note_id': start_note_id,
            'end_chapter': end_chapter,
            'block_data': block_data
        })
    
    # 确定哪些 block 需要调用 LLM
    blocks_to_generate = []  # 需要调用 LLM 的 block
    blocks_to_use_cache = {}  # 使用缓存的 block（精确匹配）
    blocks_to_update = []  # 需要覆盖的 block（开始章节号-开始笔记id相同）
    
    for block_def in all_block_definitions:
        block_id = block_def['block_id']
        start_chapter = block_def['start_chapter']
        start_note_id = block_def['start_note_id']
        end_chapter = block_def['end_chapter']
        
        # 1. 检查精确匹配（block_id 完全相同）
        if block_id in existing_blocks:
            print(f"  ✓ Block {block_def['group_idx']} 已存在（ID: {block_id}），将使用缓存")
            blocks_to_use_cache[block_id] = existing_blocks[block_id]
            continue
        
        # 2. 检查部分匹配（开始章节号-开始笔记id 相同）
        start_key = f"{start_chapter}-{start_note_id}"
        if start_key in existing_blocks_by_start:
            # 只要开始章节号-开始笔记id相同，就认为需要覆盖
            # 找到第一个匹配的 block（通常只有一个）
            existing_block_info = existing_blocks_by_start[start_key][0]
            existing_end_chapter = existing_block_info['end_chapter']
            existing_block_id = existing_block_info['block_id']
            
            print(f"  🔄 Block {block_def['group_idx']} 需要覆盖已有 block（{existing_block_id} -> {block_id}，开始章节: {start_chapter}，结束章节: {existing_end_chapter} -> {end_chapter}）")
            blocks_to_update.append({
                'new_block_def': block_def,
                'old_block_id': existing_block_id,
                'old_block_data': existing_block_info['block_data']
            })
            continue
        
        # 3. 完全新的 block，需要调用 LLM
        print(f"  ✨ Block {block_def['group_idx']} 是新的，需要调用 LLM 生成")
        blocks_to_generate.append(block_def)
    
    # 收集所有新拆分的 blocks 的 start_key（用于判断哪些旧 block 需要删除）
    new_block_start_keys = set()
    for block_def in all_block_definitions:
        start_chapter = block_def['start_chapter']
        start_note_id = block_def['start_note_id']
        start_key = f"{start_chapter}-{start_note_id}"
        new_block_start_keys.add(start_key)
    
    print(f"\n统计：")
    print(f"  - 使用缓存: {len(blocks_to_use_cache)} 个")
    print(f"  - 需要覆盖: {len(blocks_to_update)} 个")
    print(f"  - 需要生成: {len(blocks_to_generate)} 个")
    print(f"  - 新拆分的 blocks: {len(new_block_start_keys)} 个")
    
    # 第三步：只对需要生成的 block 调用 LLM
    print(f"\n第三步：调用 LLM 生成新 block...")
    new_blocks = []  # 新生成的 block，用于保存到 CSV
    
    for block_def in blocks_to_generate:
        group_idx = block_def['group_idx']
        block_id = block_def['block_id']
        mark_notes_parts = block_def['mark_notes_parts']
        review_notes_parts = block_def['review_notes_parts']
        chapter_names = block_def['chapter_names']
        
        print(f"\n[组 {group_idx}] 处理章节: {block_def['group_chapters'][0]}-{block_def['group_chapters'][-1]}（{len(block_def['group_chapters'])} 个章节，{block_def['total_notes']} 条笔记）")
        
        # 格式化划线笔记（章节标题和划线文本，用空行分隔）
        mark_notes_text = "\n\n".join(mark_notes_parts)
        
        # 格式化点评笔记（用空行分隔）
        review_notes_text = "\n\n".join(review_notes_parts) if review_notes_parts else "无点评笔记"
        
        print(f"  章节名称: {', '.join(chapter_names)}")
        print(f"  划线笔记数: {len([p for p in mark_notes_parts if p.startswith('-')])}")
        print(f"  点评笔记数: {len(review_notes_parts)}")
        print(f"  正在生成大纲（Block ID: {block_id}）...")
        
        # 生成大纲（返回字典，包含 markdown 和 html）
        outline_result = generator.generate_outline(mark_notes_text, review_notes_text)
        
        # 保存新生成的 block 到列表（稍后写入 CSV）
        from datetime import datetime
        current_time = datetime.now().isoformat()
        new_blocks.append({
            'block_id': block_id,
            'start_chapter': block_def['start_chapter'],
            'end_chapter': block_def['end_chapter'],
            'start_note_id': block_def['start_note_id'],
            'end_note_id': block_def['end_note_id'],
            'markdown': outline_result.get('markdown', ''),
            'html': outline_result.get('html', ''),
            'created_at': current_time,
            'updated_at': current_time
        })
        
        print(f"  ✓ 完成")
        
        # 添加延迟，避免 API 请求过快
        time.sleep(0.5)
    
    # 第四步：处理需要覆盖的 block（也需要调用 LLM 生成新内容）
    print(f"\n第四步：处理需要覆盖的 block（调用 LLM 生成新内容）...")
    
    for update_info in blocks_to_update:
        block_def = update_info['new_block_def']
        old_block_id = update_info['old_block_id']
        group_idx = block_def['group_idx']
        block_id = block_def['block_id']
        mark_notes_parts = block_def['mark_notes_parts']
        review_notes_parts = block_def['review_notes_parts']
        chapter_names = block_def['chapter_names']
        
        print(f"\n[组 {group_idx}] 处理章节: {block_def['group_chapters'][0]}-{block_def['group_chapters'][-1]}（覆盖 {old_block_id}）")
        
        # 格式化划线笔记
        mark_notes_text = "\n\n".join(mark_notes_parts)
        review_notes_text = "\n\n".join(review_notes_parts) if review_notes_parts else "无点评笔记"
        
        print(f"  章节名称: {', '.join(chapter_names)}")
        print(f"  划线笔记数: {len([p for p in mark_notes_parts if p.startswith('-')])}")
        print(f"  点评笔记数: {len(review_notes_parts)}")
        print(f"  正在生成大纲（Block ID: {block_id}，将覆盖 {old_block_id}）...")
        
        # 生成大纲（返回字典，包含 markdown 和 html）
        outline_result = generator.generate_outline(mark_notes_text, review_notes_text)
        
        # 保存新生成的 block（保留原有的 created_at）
        from datetime import datetime
        current_time = datetime.now().isoformat()
        old_block_data = update_info['old_block_data']
        new_blocks.append({
            'block_id': block_id,
            'start_chapter': block_def['start_chapter'],
            'end_chapter': block_def['end_chapter'],
            'start_note_id': block_def['start_note_id'],
            'end_note_id': block_def['end_note_id'],
            'markdown': outline_result.get('markdown', ''),
            'html': outline_result.get('html', ''),
            'created_at': old_block_data.get('created_at', current_time),  # 保留原有的 created_at
            'updated_at': current_time
        })
        
        print(f"  ✓ 完成（将覆盖 {old_block_id}）")
        
        # 添加延迟，避免 API 请求过快
        time.sleep(0.5)
    
    # 第五步：构建所有 block 的结果（缓存 + 新生成的）
    print(f"\n第五步：构建所有 block 的结果...")
    all_markdown_parts = []
    all_html_parts = []
    
    for block_def in all_block_definitions:
        block_id = block_def['block_id']
        group_idx = block_def['group_idx']
        group_chapters = block_def['group_chapters']
        chapter_names = block_def['chapter_names']
        
        # 确定使用哪个结果
        if block_id in blocks_to_use_cache:
            # 使用缓存
            cached_block = blocks_to_use_cache[block_id]
            outline_result = {
                'markdown': cached_block.get('markdown', ''),
                'html': cached_block.get('html', '')
            }
        else:
            # 使用新生成的（在 new_blocks 中查找）
            found_new_block = None
            for new_block in new_blocks:
                if new_block['block_id'] == block_id:
                    found_new_block = new_block
                    break
            
            if found_new_block:
                outline_result = {
                    'markdown': found_new_block.get('markdown', ''),
                    'html': found_new_block.get('html', '')
                }
            else:
                # 不应该到这里，但以防万一
                outline_result = {'markdown': '', 'html': ''}
        
        # 添加组标题
        group_title_md = f"# 第 {group_idx} 组：章节 {group_chapters[0]}-{group_chapters[-1]}\n\n"
        group_title_md += f"**章节名称**: {', '.join(chapter_names)}\n\n"
        group_title_md += f"**章节ID**: {', '.join(map(str, group_chapters))}\n\n"
        group_title_md += "---\n\n"
        
        group_title_html = f"<h1>第 {group_idx} 组：章节 {group_chapters[0]}-{group_chapters[-1]}</h1>\n"
        group_title_html += f"<p><strong>章节名称</strong>: {', '.join(chapter_names)}</p>\n"
        group_title_html += f"<p><strong>章节ID</strong>: {', '.join(map(str, group_chapters))}</p>\n"
        group_title_html += "<hr>\n"
        
        # 添加到总列表
        all_markdown_parts.append(group_title_md + outline_result.get('markdown', ''))
        all_html_parts.append(group_title_html + outline_result.get('html', ''))
        
    # 关闭客户端
    generator.close()
    
    # 保存所有 block 到 CSV（已有的 + 新生成的）
    if new_blocks or existing_blocks:
        print(f"\n正在保存 block 缓存到 CSV...")
        from datetime import datetime
        current_time = datetime.now().isoformat()
        
        # 收集需要覆盖的旧 block_id（用于删除）
        old_block_ids_to_remove = set()
        for update_info in blocks_to_update:
            old_block_ids_to_remove.add(update_info['old_block_id'])
        
        # 先添加已有的 block（除了被覆盖的，以及不在新拆分 blocks 中的）
        all_blocks_to_save = {}
        removed_old_blocks = []  # 记录被删除的旧 block
        
        for block_id, block_data in existing_blocks.items():
            # 如果这个 block 被覆盖了，跳过
            if block_id in old_block_ids_to_remove:
                continue
            
            # 从 CSV 列读取章节信息（而不是从 block_id 解析）
            block_info_from_csv = existing_blocks_info.get(block_id, {})
            start_chapter = block_info_from_csv.get('start_chapter', '')
            start_note_id = block_info_from_csv.get('start_note_id', '')
            start_key = f"{start_chapter}-{start_note_id}"
            
            # 如果这个 block 的 start_key 不在新拆分的 blocks 中，删除它
            if start_key not in new_block_start_keys:
                removed_old_blocks.append(block_id)
                continue
            
            block_info = {
                'block_id': block_id,
                'start_chapter': start_chapter,
                'end_chapter': block_info_from_csv.get('end_chapter', ''),
                'start_note_id': start_note_id,
                'end_note_id': block_info_from_csv.get('end_note_id', ''),
                'markdown': block_data.get('markdown', ''),
                'html': block_data.get('html', ''),
                'created_at': block_data.get('created_at', current_time),
                'updated_at': current_time  # 更新时间戳
            }
            
            all_blocks_to_save[block_id] = block_info
        
        # 报告删除的旧 block
        if removed_old_blocks:
            print(f"  🗑️  删除了 {len(removed_old_blocks)} 个不在新拆分 blocks 中的旧 block")
            for removed_id in removed_old_blocks[:5]:  # 只显示前 5 个
                print(f"     - {removed_id}")
            if len(removed_old_blocks) > 5:
                print(f"     ... 还有 {len(removed_old_blocks) - 5} 个")
        
        # 添加所有新生成的 block（包括覆盖的和新增的）
        for new_block in new_blocks:
            all_blocks_to_save[new_block['block_id']] = new_block
        
        updated_count = len(blocks_to_update)
        if updated_count > 0:
            print(f"  ✓ 更新了 {updated_count} 个 block（用新生成的 block 覆盖了满足条件的已有 block）")
        else:
            print(f"  ✓ 没有需要更新的 block")
        
        # 保存到 CSV
        fieldnames = ['block_id', 'start_chapter', 'end_chapter', 'start_note_id', 'end_note_id', 'markdown', 'html', 'created_at', 'updated_at']
        try:
            with open(cache_csv_file, 'w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                # 按开始章节从小到大排序
                sorted_blocks = sorted(all_blocks_to_save.values(), key=lambda x: (
                    int(x.get('start_chapter', 0)) if str(x.get('start_chapter', '0')).isdigit() else 0,
                    x.get('start_note_id', '')
                ))
                for block in sorted_blocks:
                    writer.writerow(block)
            print(f"✓ 已保存 {len(all_blocks_to_save)} 个 block 到 {cache_csv_file}")
            if new_blocks:
                new_count = len(new_blocks) - updated_count
                if updated_count > 0:
                    print(f"  - 新增: {new_count} 个")
                    print(f"  - 更新: {updated_count} 个（覆盖已有 block）")
                else:
                    print(f"  - 新增: {len(new_blocks)} 个")
                remaining_existing = len(existing_blocks) - updated_count - len(removed_old_blocks)
                if remaining_existing > 0:
                    print(f"  - 已有: {remaining_existing} 个（已保留）")
                if removed_old_blocks:
                    print(f"  - 删除: {len(removed_old_blocks)} 个（不在新拆分 blocks 中）")
        except Exception as e:
            print(f"⚠️  保存 block 缓存失败: {e}")
    
    # 从 CSV 重新读取所有 block，按顺序汇总（确保顺序正确）
    print(f"\n正在从 CSV 汇总所有 block...")
    all_blocks_sorted = []
    try:
        if cache_csv_file.exists():
            with open(cache_csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    all_blocks_sorted.append(row)
            # 按开始章节从小到大排序
            all_blocks_sorted.sort(key=lambda x: (
                int(x.get('start_chapter', 0)) if str(x.get('start_chapter', '0')).isdigit() else 0,
                x.get('start_note_id', '')
            ))
            print(f"  从 CSV 加载了 {len(all_blocks_sorted)} 个 block")
    except Exception as e:
        print(f"  ⚠️  从 CSV 读取 block 失败: {e}")
        # 如果读取失败，使用内存中的数据
        all_blocks_sorted = []
        for block_id in sorted(existing_blocks.keys()):
            block = existing_blocks[block_id]
            block['block_id'] = block_id
            all_blocks_sorted.append(block)
        for block in sorted(new_blocks, key=lambda x: (
            int(x.get('start_chapter', 0)) if str(x.get('start_chapter', '0')).isdigit() else 0,
            x.get('start_note_id', '')
        )):
            all_blocks_sorted.append(block)
    
    # 重新构建 markdown 和 HTML（从 CSV 中的 block）
    all_markdown_parts_from_csv = []
    all_html_parts_from_csv = []
    
    group_idx_from_csv = 0
    for block in all_blocks_sorted:
        group_idx_from_csv += 1
        start_chapter = block.get('start_chapter', '')
        end_chapter = block.get('end_chapter', '')
    
        # 添加组标题
        group_title_md = f"# 第 {group_idx_from_csv} 组：章节 {start_chapter}-{end_chapter}\n\n"
        group_title_md += "---\n\n"
        
        group_title_html = f"<h1>第 {group_idx_from_csv} 组：章节 {start_chapter}-{end_chapter}</h1>\n"
        group_title_html += "<hr>\n"
        
        all_markdown_parts_from_csv.append(group_title_md + block.get('markdown', ''))
        all_html_parts_from_csv.append(group_title_html + block.get('html', ''))
    
    # 合并所有大纲
    final_markdown = f"# {book_title} - 学习大纲\n\n"
    final_markdown += f"**领域**: {field}\n\n"
    final_markdown += "---\n\n"
    final_markdown += "\n\n".join(all_markdown_parts_from_csv)
    
    # 清理 HTML 中可能残留的 Markdown 代码块语法
    cleaned_html_parts = []
    for html_part in all_html_parts_from_csv:
        # 移除 Markdown 代码块标记（但保留 HTML 标签内的内容）
        cleaned = re.sub(r'```[a-z]*\n?', '', html_part)
        cleaned = re.sub(r'\n?```', '', cleaned)
        cleaned_html_parts.append(cleaned)
    
    final_html = f"<html><head><meta charset='utf-8'><title>{book_title} - 学习大纲</title></head><body>\n"
    final_html += f"<h1>{book_title} - 学习大纲</h1>\n"
    final_html += f"<p><strong>领域</strong>: {field}</p>\n"
    final_html += "<hr>\n"
    final_html += "\n".join(cleaned_html_parts)
    final_html += "</body></html>"
    
    # 生成输出文件名
    if output_file is None:
        script_dir = Path(__file__).parent  # llm/scripts
        output_dir = script_dir.parent / "output" / "outlines"  # llm/output/outlines
        output_dir.mkdir(parents=True, exist_ok=True)
        base_name = book_id
        markdown_file = str(output_dir / f"{base_name}_outline.md")
        html_file = str(output_dir / f"{base_name}_outline.html")
    else:
        # 如果指定了输出文件，使用它作为基础名称
        output_path = Path(output_file)
        base_name = output_path.stem
        output_dir = output_path.parent
        markdown_file = str(output_dir / f"{base_name}.md")
        html_file = str(output_dir / f"{base_name}.html")
    
    print(f"\n正在保存文件...")
    
    # 保存 Markdown 文件
    markdown_path = Path(markdown_file)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    with open(markdown_path, 'w', encoding='utf-8') as f:
        f.write(final_markdown)
    print(f"✓ Markdown 已保存到: {markdown_file}")
    
    # 保存 HTML 文件
    html_path = Path(html_file)
    html_path.parent.mkdir(parents=True, exist_ok=True)
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(final_html)
    print(f"✓ HTML 已保存到: {html_file}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='学习大纲生成工具：从笔记 CSV 文件中按章节分组，使用 Gemini API 生成学习大纲',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  # 使用 bookID
  python generate_outline.py --book-id 3300089819
  python generate_outline.py --book-id 3300089819 --output llm/output/outlines/book_outline.md
  
  # 使用书名
  python generate_outline.py --book-name "书名"
  python generate_outline.py --book-name "书名" --role 学习者
  
  # 先重新 fetch 数据，再生成 outline
  python generate_outline.py --book-name "书名" --fetch
  python generate_outline.py --book-id 3300089819 --fetch
        """
    )
    
    # 书名和 bookID 二选一
    book_group = parser.add_mutually_exclusive_group(required=True)
    book_group.add_argument('--book-name', '--book-title', dest='book_title', type=str,
                           help='书籍名称')
    book_group.add_argument('--book-id', '--id', dest='book_id', type=str,
                           help='书籍ID')
    
    parser.add_argument('--output', '--output-file', dest='output_file', type=str, default=None,
                       help='输出的 Markdown/HTML 文件路径（可选，默认自动生成）')
    parser.add_argument('--role', type=str, default='学习者',
                       help='角色（可选，默认为"学习者"）')
    parser.add_argument('--api-key', type=str,
                       help='Gemini API 密钥（可选，优先从环境变量 GEMINI_API_KEY 或 GOOGLE_API_KEY 读取）')
    parser.add_argument('--fetch', '--refresh-data', dest='fetch_data', action='store_true',
                       help='在生成 outline 之前，先重新 fetch 笔记数据（调用 wereader/fetch.py）')
    
    args = parser.parse_args()
    
    # 获取 API 密钥（优先从命令行参数，其次从环境变量）
    api_key = args.api_key or os.environ.get('GOOGLE_API_KEY') or os.environ.get('GEMINI_API_KEY')
    
    if not api_key:
        print("错误：请设置 GEMINI_API_KEY 或 GOOGLE_API_KEY 环境变量，或使用 --api-key 参数")
        sys.exit(1)
    
    try:
        process_csv_file(
            book_id=args.book_id,
            book_title=args.book_title,
            output_file=args.output_file,
            api_key=api_key,
            role=args.role,
            fetch_data=args.fetch_data
        )
    except KeyboardInterrupt:
        print("\n\n用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n错误：{e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

