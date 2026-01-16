#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
概念提取工具
从笔记 CSV 文件中提取概念词，使用 Gemini API 生成定义
"""

import sys
import os
import csv
import json
import time
import re
import argparse
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Set
from collections import defaultdict
from datetime import datetime
from google import genai

# 导入 prompt 模板
try:
    # 从项目根目录运行时
    from llm.prompts import (
        EXTRACT_CONCEPTS_PROMPT_TEMPLATE,
        DEDUPLICATE_CONCEPTS_PROMPT_TEMPLATE,
        GET_CONCEPT_CATEGORY_PROMPT_TEMPLATE,
        GET_CONCEPT_DEFINITION_HTML_PROMPT_TEMPLATE,
        GET_SHORT_DEFINITION_PROMPT_TEMPLATE
    )
except ImportError:
    # 从 llm 目录运行时
    from prompts import (
        EXTRACT_CONCEPTS_PROMPT_TEMPLATE,
        DEDUPLICATE_CONCEPTS_PROMPT_TEMPLATE,
        GET_CONCEPT_CATEGORY_PROMPT_TEMPLATE,
        GET_CONCEPT_DEFINITION_HTML_PROMPT_TEMPLATE,
        GET_SHORT_DEFINITION_PROMPT_TEMPLATE
    )


def is_valid_html(html_content: str) -> bool:
    """
    验证字符串是否为有效的HTML格式
    
    Args:
        html_content: 待验证的字符串
    
    Returns:
        如果是有效的HTML格式返回True，否则返回False
    """
    if not html_content or not html_content.strip():
        return False
    
    html_content = html_content.strip()
    
    # 检查是否包含HTML标签（至少有一个开始标签和结束标签）
    # 简单的验证：检查是否包含 < 和 >，并且有配对的标签
    if '<' not in html_content or '>' not in html_content:
        return False
    
    # 检查是否包含常见的HTML标签（如 <p>, <div>, <span>, <h1> 等）
    html_tags = ['<p>', '</p>', '<div>', '</div>', '<span>', '</span>', 
                 '<h1>', '</h1>', '<h2>', '</h2>', '<h3>', '</h3>',
                 '<ul>', '</ul>', '<ol>', '</ol>', '<li>', '</li>',
                 '<strong>', '</strong>', '<em>', '</em>', '<br>', '<br/>']
    
    has_html_tag = any(tag in html_content for tag in html_tags)
    
    # 如果包含HTML标签，认为是有效的HTML
    if has_html_tag:
        return True
    
    # 如果没有常见标签，但包含 < 和 >，检查是否有基本的HTML结构
    # 至少应该有一个开始标签和一个结束标签
    open_tags = re.findall(r'<[^/][^>]*>', html_content)
    close_tags = re.findall(r'</[^>]+>', html_content)
    
    # 如果有开始标签和结束标签，认为是有效的HTML
    if open_tags and close_tags:
        return True
    
    return False


class ConceptExtractor:
    """使用 Gemini API 提取概念"""
    
    def __init__(self, api_key: Optional[str] = None, max_retries: int = 3):
        """
        初始化 Gemini API 客户端
        
        Args:
            api_key: Gemini API 密钥，如果为 None 则从环境变量读取
        """
        if api_key is None:
            api_key = os.environ.get('GOOGLE_API_KEY') or os.environ.get('GEMINI_API_KEY')
        
        if not api_key:
            raise ValueError(
                "请提供 Gemini API 密钥。可以通过以下方式：\n"
                "1. 作为参数传入：ConceptExtractor(api_key='your_key')\n"
                "2. 设置环境变量：export GEMINI_API_KEY='your_api_key' 或 export GOOGLE_API_KEY='your_api_key'"
            )
        
        self.client = genai.Client(api_key=api_key)
        self.max_retries = max_retries
    
    def _is_rate_limit_error(self, error: Exception) -> bool:
        """
        检查是否是限流错误（429）
        
        Args:
            error: 异常对象
        
        Returns:
            如果是 429 错误返回 True，否则返回 False
        """
        error_str = str(error).upper()
        return '429' in error_str or 'RESOURCE_EXHAUSTED' in error_str or 'RATE_LIMIT' in error_str
    
    def extract_concepts(self, mark_texts: List[str], domain: str) -> List[str]:
        """
        从文本中提取概念词（只返回概念名称，不包含定义）
        
        Args:
            mark_texts: 文本列表（每10行为一组）
            domain: 领域
        
        Returns:
            概念词列表
        """
        text_content = '\n'.join(mark_texts)
        
        prompt = EXTRACT_CONCEPTS_PROMPT_TEMPLATE.replace("{{domain}}", domain)
        prompt = prompt.replace("{{text_content}}", text_content)
        
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                response = self.client.models.generate_content(
                    model='gemini-2.0-flash-001',
                    contents=prompt,
                )
                
                if hasattr(response, 'text'):
                    response_text = response.text
                elif hasattr(response, 'candidates') and len(response.candidates) > 0:
                    response_text = response.candidates[0].content.parts[0].text
                else:
                    response_text = str(response)
                
                response_text = response_text.strip()
                
                # 解析概念词列表
                concepts = []
                for line in response_text.split('\n'):
                    line = line.strip()
                    if line and line != '无' and not line.startswith('#'):
                        # 移除可能的编号（如 "1. ", "1、"等）
                        line = re.sub(r'^\d+[\.、]\s*', '', line)
                        if line:
                            concepts.append(line)
                
                return concepts
                
            except Exception as e:
                last_exception = e
                
                # 检查是否是 429 限流错误
                if self._is_rate_limit_error(e):
                    if attempt < self.max_retries:
                        print(f"  ⚠️  遇到限流错误（429），等待 5 秒后重试（第 {attempt + 1}/{self.max_retries} 次尝试）...")
                        time.sleep(5)
                        continue
                    else:
                        print(f"  ⚠️  提取概念时出错（429 限流，已重试 {self.max_retries} 次）: {e}")
                        return []
                else:
                    # 其他错误，不重试
                    print(f"  ⚠️  提取概念时出错: {e}")
                    return []
        
        print(f"  ⚠️  提取概念失败（重试 {self.max_retries} 次后）: {last_exception}")
        return []
    
    def deduplicate_concepts(self, all_concepts: List[str]) -> List[str]:
        """
        对概念词进行去重（概念和形式）
        
        Args:
            all_concepts: 所有概念词列表
        
        Returns:
            去重后的概念词列表
        """
        if not all_concepts:
            return []
        
        concepts_text = '\n'.join(all_concepts)
        
        prompt = DEDUPLICATE_CONCEPTS_PROMPT_TEMPLATE.replace("{{concepts_text}}", concepts_text)
        
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                response = self.client.models.generate_content(
                    model='gemini-2.0-flash-001',
                    contents=prompt,
                )
                
                if hasattr(response, 'text'):
                    response_text = response.text
                elif hasattr(response, 'candidates') and len(response.candidates) > 0:
                    response_text = response.candidates[0].content.parts[0].text
                else:
                    response_text = str(response)
                
                response_text = response_text.strip()
                
                # 解析去重后的概念词列表
                deduplicated = []
                for line in response_text.split('\n'):
                    line = line.strip()
                    if line and not line.startswith('#'):
                        line = re.sub(r'^\d+[\.、]\s*', '', line)
                        if line:
                            deduplicated.append(line)
                
                return deduplicated
                
            except Exception as e:
                last_exception = e
                
                # 检查是否是 429 限流错误
                if self._is_rate_limit_error(e):
                    if attempt < self.max_retries:
                        print(f"  ⚠️  遇到限流错误（429），等待 5 秒后重试（第 {attempt + 1}/{self.max_retries} 次尝试）...")
                        time.sleep(5)
                        continue
                    else:
                        print(f"  ⚠️  去重时出错（429 限流，已重试 {self.max_retries} 次）: {e}")
                        return list(set(all_concepts))  # 如果失败，使用简单的去重
                else:
                    # 其他错误，不重试
                    print(f"  ⚠️  去重时出错: {e}")
                    return list(set(all_concepts))  # 如果失败，使用简单的去重
        
        print(f"  ⚠️  去重失败（重试 {self.max_retries} 次后）: {last_exception}")
        return list(set(all_concepts))  # 如果失败，使用简单的去重
    
    def get_concept_category(self, concept: str, domain: str) -> str:
        """
        获取概念在领域中的子分类
        
        Args:
            concept: 概念词
            domain: 领域
        
        Returns:
            子分类名称
        """
        prompt = GET_CONCEPT_CATEGORY_PROMPT_TEMPLATE.replace("{{concept}}", concept)
        prompt = prompt.replace("{{domain}}", domain)
        
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                response = self.client.models.generate_content(
                    model='gemini-2.0-flash-001',
                    contents=prompt,
                )
                
                if hasattr(response, 'text'):
                    category = response.text.strip()
                elif hasattr(response, 'candidates') and len(response.candidates) > 0:
                    category = response.candidates[0].content.parts[0].text.strip()
                else:
                    category = "其他"
                
                # 清理可能的额外内容
                category = category.split('\n')[0].strip()
                if not category or category == '无':
                    category = "其他"
                
                return category
                
            except Exception as e:
                last_exception = e
                
                # 检查是否是 429 限流错误
                if self._is_rate_limit_error(e):
                    if attempt < self.max_retries:
                        print(f"  ⚠️  遇到限流错误（429），等待 5 秒后重试（第 {attempt + 1}/{self.max_retries} 次尝试）...")
                        time.sleep(5)
                        continue
                    else:
                        print(f"  ⚠️  获取分类时出错（429 限流，已重试 {self.max_retries} 次）: {e}")
                        return "其他"
                else:
                    # 其他错误，不重试
                    print(f"  ⚠️  获取分类时出错: {e}")
                    return "其他"
        
        print(f"  ⚠️  获取分类失败（重试 {self.max_retries} 次后）: {last_exception}")
        return "其他"
    
    def find_sentences_with_concept(self, rows: List[Dict[str, str]], concept: str, min_notes: int = 30) -> tuple[List[str], str]:
        """
        找到概念词出现次数最多的章节组，返回该组的所有文本和章节范围
        确保返回的文本至少包含 min_notes 个笔记（如果章节笔记不足，合并下一章节）
        
        Args:
            rows: CSV 行数据
            concept: 概念词
            min_notes: 最少笔记数量（默认30）
        
        Returns:
            (相关句子列表, 章节范围字符串 a-b)
        """
        # 按章节分组
        chapters_dict = defaultdict(list)
        for row in rows:
            chapter_uid = row.get('chapterUid', '').strip()
            if chapter_uid:
                try:
                    uid = int(chapter_uid)
                    chapters_dict[uid].append(row)
                except ValueError:
                    continue
        
        if not chapters_dict:
            return [], ""
        
        # 按章节ID排序
        sorted_chapters = sorted(chapters_dict.keys())
        
        # 统计每个章节中概念词出现的次数
        chapter_counts = {}
        for chapter_uid, chapter_rows in chapters_dict.items():
            count = 0
            for row in chapter_rows:
                mark_text = row.get('markText', '').strip()
                if mark_text and concept in mark_text:
                    count += mark_text.count(concept)
            chapter_counts[chapter_uid] = count
        
        # 找到出现次数最多的章节
        if not chapter_counts or max(chapter_counts.values()) == 0:
            # 如果没有找到包含概念的章节，返回空列表和空字符串
            return [], ""
        
        max_chapter_uid = max(chapter_counts.items(), key=lambda x: x[1])[0]
        
        # 找到该章节在排序列表中的位置
        max_chapter_idx = sorted_chapters.index(max_chapter_uid)
        
        # 从该章节开始，累积到至少 min_notes 个笔记
        group_rows = []
        total_notes = 0
        chapter_range_start = None
        chapter_range_end = None
        
        i = max_chapter_idx
        while i < len(sorted_chapters) and total_notes < min_notes:
            chapter_uid = sorted_chapters[i]
            chapter_rows = chapters_dict[chapter_uid]
            group_rows.extend(chapter_rows)
            
            # 记录章节范围
            if chapter_range_start is None:
                chapter_range_start = chapter_uid
            chapter_range_end = chapter_uid
            
            # 统计该章节的笔记数量
            mark_texts_count = len([row for row in chapter_rows if row.get('markText', '').strip()])
            total_notes += mark_texts_count
            i += 1
        
        # 返回该组的所有 markText（按 createTime 排序）
        sentences = []
        sorted_group_rows = sorted(
            group_rows,
            key=lambda x: int(x.get('createTime', 0)) if x.get('createTime', '').strip().isdigit() else 0
        )
        
        for row in sorted_group_rows:
            mark_text = row.get('markText', '').strip()
            if mark_text:
                sentences.append(mark_text)
        
        # 生成章节范围字符串
        if chapter_range_start is not None and chapter_range_end is not None:
            if chapter_range_start == chapter_range_end:
                chapter_range = str(chapter_range_start)
            else:
                chapter_range = f"{chapter_range_start}-{chapter_range_end}"
        else:
            chapter_range = ""
        
        return sentences, chapter_range
    
    def get_concept_definition_html(self, concept: str, sentences: List[str], domain: str) -> str:
        """
        生成概念的 HTML 格式定义（带重试机制：如果返回的不是纯HTML格式则重试）
        
        Args:
            concept: 概念词
            sentences: 相关句子列表
            domain: 领域
        
        Returns:
            HTML 格式的定义
        """
        sentences_text = '\n'.join([f"<p>{s}</p>" for s in sentences])
        
        prompt = GET_CONCEPT_DEFINITION_HTML_PROMPT_TEMPLATE.replace("{{concept}}", concept)
        prompt = prompt.replace("{{domain}}", domain)
        prompt = prompt.replace("{{sentences_text}}", sentences_text)
        
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                response = self.client.models.generate_content(
                    model='gemini-2.0-flash-001',
                    contents=prompt,
                )
                
                if hasattr(response, 'text'):
                    html_content = response.text.strip()
                elif hasattr(response, 'candidates') and len(response.candidates) > 0:
                    html_content = response.candidates[0].content.parts[0].text.strip()
                else:
                    html_content = f"<p>无法生成定义</p>"
                
                # 清理可能的 markdown 代码块标记和引号
                html_content = re.sub(r'^```[a-z]*\n?', '', html_content, flags=re.MULTILINE)
                html_content = re.sub(r'\n?```$', '', html_content, flags=re.MULTILINE)
                html_content = html_content.strip()
                # 移除前后引号（如果存在）
                if html_content.startswith('"') and html_content.endswith('"'):
                    html_content = html_content[1:-1]
                if html_content.startswith("'") and html_content.endswith("'"):
                    html_content = html_content[1:-1]
                
                html_content = html_content.strip()
                
                # 验证是否为有效的HTML格式
                if is_valid_html(html_content):
                    return html_content
                else:
                    # 如果不是有效的HTML，记录并重试
                    if attempt < self.max_retries:
                        print(f"  ⚠️  返回内容不是有效的HTML格式（第 {attempt + 1} 次尝试），重试...")
                        print(f"     返回内容预览: {html_content[:100]}...")
                        continue
                    else:
                        # 最后一次尝试，即使不是有效HTML也返回
                        print(f"  ⚠️  返回内容不是有效的HTML格式（已重试 {self.max_retries} 次），使用返回内容")
                        return html_content if html_content else "<p>无法生成定义</p>"
                
            except Exception as e:
                last_exception = e
                error_msg = str(e).lower()
                
                # 检查是否是 429 限流错误
                if self._is_rate_limit_error(e):
                    if attempt < self.max_retries:
                        print(f"  ⚠️  遇到限流错误（429），等待 5 秒后重试（第 {attempt + 1}/{self.max_retries} 次尝试）...")
                        time.sleep(5)
                        continue
                    else:
                        print(f"  ⚠️  生成定义时出错（429 限流，已重试 {self.max_retries} 次）: {e}")
                        return f"<p>生成定义时出错: {str(e)}</p>"
                
                # 某些错误不应该重试（如认证错误、参数错误）
                if any(keyword in error_msg for keyword in ['auth', 'permission', 'invalid', 'not found', '404']):
                    print(f"  ⚠️  生成定义时出错（不可重试）: {e}")
                    return f"<p>生成定义时出错: {str(e)}</p>"
                
                # 如果是最后一次尝试，返回错误信息
                if attempt == self.max_retries:
                    break
                
                # 打印重试信息
                print(f"  ⚠️  生成定义失败（第 {attempt + 1} 次尝试）: {e}，重试...")
        
        # 所有重试都失败，返回错误信息
        print(f"  ⚠️  生成定义失败（重试 {self.max_retries} 次后）: {last_exception}")
        return f"<p>生成定义时出错: {str(last_exception)}</p>"
    
    def get_short_definition(self, concept: str, domain: str) -> str:
        """
        生成概念的短定义（30字符以内）
        
        Args:
            concept: 概念词
            domain: 领域
        
        Returns:
            短定义文本
        """
        prompt = GET_SHORT_DEFINITION_PROMPT_TEMPLATE.replace("{{concept}}", concept)
        prompt = prompt.replace("{{domain}}", domain)
        
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                response = self.client.models.generate_content(
                    model='gemini-2.0-flash-001',
                    contents=prompt,
                )
                
                if hasattr(response, 'text'):
                    definition = response.text.strip()
                elif hasattr(response, 'candidates') and len(response.candidates) > 0:
                    definition = response.candidates[0].content.parts[0].text.strip()
                else:
                    definition = "概念定义"
                
                # 清理可能的额外内容
                definition = definition.split('\n')[0].strip()
                # 限制长度
                if len(definition) > 30:
                    definition = definition[:27] + "..."
                
                return definition
                
            except Exception as e:
                last_exception = e
                
                # 检查是否是 429 限流错误
                if self._is_rate_limit_error(e):
                    if attempt < self.max_retries:
                        print(f"  ⚠️  遇到限流错误（429），等待 5 秒后重试（第 {attempt + 1}/{self.max_retries} 次尝试）...")
                        time.sleep(5)
                        continue
                    else:
                        print(f"  ⚠️  生成短定义时出错（429 限流，已重试 {self.max_retries} 次）: {e}")
                        return "概念定义"
                else:
                    # 其他错误，不重试
                    print(f"  ⚠️  生成短定义时出错: {e}")
                    return "概念定义"
        
        print(f"  ⚠️  生成短定义失败（重试 {self.max_retries} 次后）: {last_exception}")
        return "概念定义"
    
    def close(self):
        """关闭客户端"""
        if hasattr(self, 'client'):
            try:
                self.client.close()
            except:
                pass


def read_csv_file(csv_file: str) -> List[Dict[str, str]]:
    """读取 CSV 文件"""
    rows = []
    csv_path = Path(csv_file)
    
    if not csv_path.exists():
        print(f"错误：文件不存在: {csv_file}")
        return rows
    
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
    except Exception as e:
        print(f"读取文件时出错: {e}")
    
    return rows


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


def process_csv_file(book_id: Optional[str] = None, book_title: Optional[str] = None, output_file: Optional[str] = None, api_key: Optional[str] = None, max_retries: int = 3, fetch_data: bool = False):
    """
    处理 CSV 文件，提取概念
    
    Args:
        book_id: 书籍ID（与 book_title 二选一）
        book_title: 书名（与 book_id 二选一）
        output_file: 输出的 CSV 文件路径
        api_key: Gemini API 密钥
        max_retries: 最大重试次数
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
            print(f"\n✓ 数据已更新，继续提取概念...\n")
    
    # 默认路径
    notebooks_csv = project_root / "wereader" / "output" / "fetch_notebooks_output.csv"
    notes_dir = project_root / "wereader" / "output" / "notes"
    
    # 1. 确定 bookId 和书籍信息
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
    
    # 获取书籍信息（优先使用从 CSV 查找的信息）
    if book_info:
        book_title = book_info.get('title', '未知书籍')
        domain = book_info.get('categories', '未知领域')
    else:
        first_row = rows[0] if rows else {}
        book_title = first_row.get('title', book_title_display if 'book_title_display' in locals() else '未知书籍')
        domain = first_row.get('categories', '未知领域')
    
    print(f"书籍: {book_title}")
    print(f"领域: {domain}\n")
    
    # 初始化提取器
    extractor = ConceptExtractor(api_key=api_key, max_retries=max_retries)
    
    # 按章节分组
    chapters_dict = defaultdict(list)
    for row in rows:
        chapter_uid = row.get('chapterUid', '').strip()
        if chapter_uid:
            try:
                uid = int(chapter_uid)
                chapters_dict[uid].append(row)
            except ValueError:
                continue
    
    # 按章节ID排序
    sorted_chapters = sorted(chapters_dict.keys())
    
    # 检查输出文件是否已存在，确定从哪个章节开始处理
    if output_file is None:
        script_dir = Path(__file__).parent  # llm/scripts
        output_dir = script_dir.parent / "output" / "concepts"  # llm/output/concepts
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file_path = output_dir / f"{book_id}_concepts.csv"
    else:
        output_file_path = Path(output_file)
        output_file_path.parent.mkdir(parents=True, exist_ok=True)
    
    # 如果文件已存在，找到最后一个出现的chapterID
    last_chapter_id = None
    if output_file_path.exists():
        print(f"\n检测到已存在的概念文件: {output_file_path}")
        try:
            with open(output_file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                max_chapter_id = None
                for row in reader:
                    chapter_range = row.get('chapterRange', '').strip()
                    if chapter_range:
                        # 解析chapterRange，可能是单个数字（如 "5"）或范围（如 "5-10"）
                        try:
                            if '-' in chapter_range:
                                # 范围格式：提取结束的chapterID
                                parts = chapter_range.split('-')
                                if len(parts) == 2:
                                    end_id = int(parts[1].strip())
                                    if max_chapter_id is None or end_id > max_chapter_id:
                                        max_chapter_id = end_id
                            else:
                                # 单个数字格式
                                chapter_id = int(chapter_range.strip())
                                if max_chapter_id is None or chapter_id > max_chapter_id:
                                    max_chapter_id = chapter_id
                        except ValueError:
                            continue
                
                if max_chapter_id is not None:
                    last_chapter_id = max_chapter_id
                    print(f"  找到最后一个处理的章节ID: {last_chapter_id}")
                    print(f"  将从章节 {last_chapter_id + 1} 开始处理（跳过已处理的章节）")
        except Exception as e:
            print(f"  ⚠️  读取已有概念文件失败: {e}")
    
    # 第一步：提取概念词（按章节分组处理）
    print("\n" + "=" * 60)
    print("第一步：提取概念词（按章节分组处理）")
    print("=" * 60)
    
    all_concepts = []
    
    # 按章节逐个处理，跳过已处理的章节
    processed_count = 0
    skipped_count = 0
    
    for i, chapter_uid in enumerate(sorted_chapters, 1):
        # 如果设置了last_chapter_id，跳过已处理的章节
        if last_chapter_id is not None and chapter_uid <= last_chapter_id:
            skipped_count += 1
            chapter_name = chapters_dict[chapter_uid][0].get('chapterName', f'章节{chapter_uid}') if chapters_dict[chapter_uid] else f'章节{chapter_uid}'
            print(f"\n[{i}/{len(sorted_chapters)}] 跳过章节 {chapter_uid}: {chapter_name}（已处理）")
            continue
        chapter_rows = chapters_dict[chapter_uid]
        
        # 提取该章节的 markText
        mark_texts = [row.get('markText', '').strip() for row in chapter_rows if row.get('markText', '').strip()]
        
        if mark_texts:
            chapter_name = chapter_rows[0].get('chapterName', f'章节{chapter_uid}') if chapter_rows else f'章节{chapter_uid}'
            
            print(f"\n[{i}/{len(sorted_chapters)}] 处理章节 {chapter_uid}: {chapter_name}（{len(mark_texts)} 条笔记）...")
            concepts = extractor.extract_concepts(mark_texts, domain)
            
            if concepts:
                print(f"  提取到 {len(concepts)} 个概念: {', '.join(concepts[:5])}{'...' if len(concepts) > 5 else ''}")
                all_concepts.extend(concepts)
                processed_count += 1
            else:
                print(f"  未提取到概念")
            time.sleep(0.5)  # 避免请求过快
        else:
            chapter_name = chapter_rows[0].get('chapterName', f'章节{chapter_uid}') if chapter_rows else f'章节{chapter_uid}'
            print(f"\n[{i}/{len(sorted_chapters)}] 跳过章节 {chapter_uid}: {chapter_name}（无笔记）")
    
    if skipped_count > 0:
        print(f"\n跳过 {skipped_count} 个已处理的章节")
    if processed_count > 0:
        print(f"处理了 {processed_count} 个新章节")
    print(f"\n共提取到 {len(all_concepts)} 个概念词（含重复）")
    
    # 第二步：去重
    print("\n" + "=" * 60)
    print("第二步：去重（概念和形式）")
    print("=" * 60)
    
    # 如果本次没有提取到新概念，直接加载已有概念并返回
    if not all_concepts:
        print(f"\n⚠️  本次未提取到新概念")
        if output_file_path.exists():
            print(f"  将保留已有的概念文件")
        return
    
    deduplicated_concepts = extractor.deduplicate_concepts(all_concepts)
    print(f"去重后剩余 {len(deduplicated_concepts)} 个概念")
    
    # 检查输出文件是否已存在，加载已有的概念
    existing_concepts = {}
    
    # 如果文件已存在，读取已有的概念
    if output_file_path.exists():
        print(f"\n检测到已存在的概念文件: {output_file_path}")
        try:
            with open(output_file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    concept_name = row.get('concept', '').strip()
                    if concept_name:
                        existing_concepts[concept_name] = row
            print(f"  已加载 {len(existing_concepts)} 个已有概念")
        except Exception as e:
            print(f"  ⚠️  读取已有概念文件失败: {e}")
    
    # 第三步：为每个概念生成详细信息
    print("\n" + "=" * 60)
    print("第三步：生成概念详细信息")
    print("=" * 60)
    
    concept_results = []
    skipped_count = 0
    
    for idx, concept in enumerate(deduplicated_concepts, 1):
        print(f"\n[{idx}/{len(deduplicated_concepts)}] 处理概念: {concept}")
        
        # 检查概念是否已存在
        if concept in existing_concepts:
            print(f"  ✓ 概念已存在，跳过生成（使用已有数据）")
            existing_concept = existing_concepts[concept]
            # 更新时间戳
            existing_concept['updated_at'] = datetime.now().isoformat()
            concept_results.append(existing_concept)
            skipped_count += 1
            continue
        
        # 获取子分类
        print(f"  获取子分类...")
        category = extractor.get_concept_category(concept, domain)
        print(f"  子分类: {category}")
        time.sleep(0.3)
        
        # 找到相关句子和章节范围
        source_sentences, chapter_range = extractor.find_sentences_with_concept(rows, concept)
        sentences_html = '\n'.join([f"<p>{s}</p>" for s in source_sentences])
        
        # 生成 HTML 定义
        print(f"  生成 HTML 定义...")
        html_definition = extractor.get_concept_definition_html(concept, source_sentences, domain)
        time.sleep(0.5)
        
        # 生成短定义
        print(f"  生成短定义...")
        short_def = extractor.get_short_definition(concept, domain)
        print(f"  短定义: {short_def}")
        time.sleep(0.3)
        
        # 生成 conceptId: bookId_概念名
        concept_id = f"{book_id}_{concept}"
        
        concept_results.append({
            'conceptId': concept_id,
            'bookId': book_id,
            'concept': concept,
            'domain': domain,
            'category': category,
            'source': book_title,
            'chapterRange': chapter_range,
            'sentences': sentences_html,
            'short_definition': short_def,
            'definition': html_definition
        })
    
    if skipped_count > 0:
        print(f"\n跳过 {skipped_count} 个已存在的概念（使用已有数据）")
    
    # 关闭客户端
    extractor.close()
    
    # 保存到 CSV（使用之前确定的 output_file_path）
    print(f"\n正在保存到: {output_file_path}")
    
    fieldnames = ['conceptId', 'bookId', 'concept', 'domain', 'category', 'source', 'chapterRange', 'sentences', 'short_definition', 'definition', 'created_at', 'updated_at']
    
    # Get current timestamp
    current_time = datetime.now().isoformat()
    
    # 构建要保存的所有概念：合并新生成的概念和所有已有概念
    # 1. 先添加新生成的概念（concept_results 中包含了新生成的和本次更新的已有概念）
    all_concepts_to_save = {}
    for result in concept_results:
        concept_name = result.get('concept', '').strip()
        if concept_name:
            # 如果已有 created_at，保留它；否则使用当前时间
            if 'created_at' not in result or not result.get('created_at'):
                result['created_at'] = current_time
            # updated_at 已经在处理时更新了
            if 'updated_at' not in result:
                result['updated_at'] = current_time
            all_concepts_to_save[concept_name] = result
    
    # 2. 添加不在本次处理中的已有概念（保留它们，避免丢失）
    concepts_in_current_run = set(concept.get('concept', '').strip() for concept in concept_results)
    preserved_count = 0
    for concept_name, existing_concept in existing_concepts.items():
        if concept_name not in concepts_in_current_run:
            # 这个已有概念不在本次处理中，需要保留
            all_concepts_to_save[concept_name] = existing_concept
            preserved_count += 1
    
    try:
        with open(output_file_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            # 按概念名称排序，确保输出顺序一致
            for concept_name in sorted(all_concepts_to_save.keys()):
                writer.writerow(all_concepts_to_save[concept_name])
        
        new_concepts_count = len(concept_results) - skipped_count
        total_concepts_count = len(all_concepts_to_save)
        print(f"✓ 成功保存 {total_concepts_count} 个概念到 {output_file_path}")
        if skipped_count > 0:
            print(f"  - 新增: {new_concepts_count} 个")
            print(f"  - 更新: {skipped_count} 个（已保留并更新时间戳）")
        if preserved_count > 0:
            print(f"  - 保留: {preserved_count} 个（不在本次处理中，已保留）")
    except Exception as e:
        print(f"✗ 保存文件时出错: {e}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='概念提取工具：从笔记 CSV 文件中提取概念词，使用 Gemini API 生成定义',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  # 使用 bookID
  python extract_concepts.py --book-id 3300089819
  python extract_concepts.py --book-id 3300089819 --output llm/output/concepts/book_concepts.csv
  
  # 使用书名
  python extract_concepts.py --book-name "书名"
        """
    )
    
    # 书名和 bookID 二选一
    book_group = parser.add_mutually_exclusive_group(required=True)
    book_group.add_argument('--book-name', '--book-title', dest='book_title', type=str,
                           help='书籍名称')
    book_group.add_argument('--book-id', '--id', dest='book_id', type=str,
                           help='书籍ID')
    
    parser.add_argument('--output', '--output-file', dest='output_file', type=str, default=None,
                       help='输出的概念 CSV 文件路径（可选，默认自动生成到 llm/output/concepts/）')
    parser.add_argument('--api-key', type=str,
                       help='Gemini API 密钥（可选，优先从环境变量 GEMINI_API_KEY 或 GOOGLE_API_KEY 读取）')
    
    args = parser.parse_args()
    
    # 获取 API 密钥（优先从命令行参数，其次从环境变量）
    api_key = args.api_key or os.environ.get('GOOGLE_API_KEY') or os.environ.get('GEMINI_API_KEY')
    
    if not api_key:
        print("错误：请设置 GEMINI_API_KEY 或 GOOGLE_API_KEY 环境变量，或使用 --api-key 参数")
        sys.exit(1)
    
    process_csv_file(
        book_id=args.book_id,
        book_title=args.book_title,
        output_file=args.output_file,
        api_key=api_key,
        max_retries=args.max_retries
    )


if __name__ == "__main__":
    main()

