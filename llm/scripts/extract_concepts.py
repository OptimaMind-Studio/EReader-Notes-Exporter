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
from pathlib import Path
from typing import Optional, List, Dict, Set
from collections import defaultdict
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


class ConceptExtractor:
    """使用 Gemini API 提取概念"""
    
    def __init__(self, api_key: Optional[str] = None):
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
            print(f"  ⚠️  提取概念时出错: {e}")
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
            print(f"  ⚠️  去重时出错: {e}")
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
            print(f"  ⚠️  获取分类时出错: {e}")
            return "其他"
    
    def find_sentences_with_concept(self, rows: List[Dict[str, str]], concept: str, min_notes: int = 30) -> List[str]:
        """
        找到概念词出现次数最多的章节组，返回该组的所有文本
        确保返回的文本至少包含 min_notes 个笔记（如果章节笔记不足，合并下一章节）
        
        Args:
            rows: CSV 行数据
            concept: 概念词
            min_notes: 最少笔记数量（默认30）
        
        Returns:
            相关句子列表（完整章节组的文本，至少 min_notes 个笔记）
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
            return []
        
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
            # 如果没有找到包含概念的章节，返回空列表
            return []
        
        max_chapter_uid = max(chapter_counts.items(), key=lambda x: x[1])[0]
        
        # 找到该章节在排序列表中的位置
        max_chapter_idx = sorted_chapters.index(max_chapter_uid)
        
        # 从该章节开始，累积到至少 min_notes 个笔记
        group_rows = []
        total_notes = 0
        
        i = max_chapter_idx
        while i < len(sorted_chapters) and total_notes < min_notes:
            chapter_uid = sorted_chapters[i]
            chapter_rows = chapters_dict[chapter_uid]
            group_rows.extend(chapter_rows)
            
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
        
        return sentences
    
    def get_concept_definition_html(self, concept: str, sentences: List[str], domain: str) -> str:
        """
        生成概念的 HTML 格式定义
        
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
            
            return html_content.strip()
            
        except Exception as e:
            print(f"  ⚠️  生成定义时出错: {e}")
            return f"<p>生成定义时出错: {str(e)}</p>"
    
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
            print(f"  ⚠️  生成短定义时出错: {e}")
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


def process_csv_file(book_id: Optional[str] = None, book_title: Optional[str] = None, output_file: Optional[str] = None, api_key: Optional[str] = None):
    """
    处理 CSV 文件，提取概念
    
    Args:
        book_id: 书籍ID（与 book_title 二选一）
        book_title: 书名（与 book_id 二选一）
        output_file: 输出的 CSV 文件路径
        api_key: Gemini API 密钥
    """
    # 获取脚本所在目录
    script_dir = Path(__file__).parent  # llm/scripts
    project_root = script_dir.parent.parent  # 项目根目录
    
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
    extractor = ConceptExtractor(api_key=api_key)
    
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
    
    # 第一步：提取概念词（按章节分组，每组至少30个笔记）
    print("=" * 60)
    print("第一步：提取概念词（按章节分组，每组至少30个笔记）")
    print("=" * 60)
    
    all_concepts = []
    min_notes_per_group = 30
    
    i = 0
    while i < len(sorted_chapters):
        # 收集当前组的所有章节
        group_chapters = []
        group_rows = []
        total_notes = 0
        
        # 从当前章节开始，累积到至少10个笔记
        j = i
        while j < len(sorted_chapters) and total_notes < min_notes_per_group:
            chapter_uid = sorted_chapters[j]
            chapter_rows = chapters_dict[chapter_uid]
            mark_texts_count = len([row for row in chapter_rows if row.get('markText', '').strip()])
            
            group_chapters.append(chapter_uid)
            group_rows.extend(chapter_rows)
            total_notes += mark_texts_count
            j += 1
        
        # 提取该组的 markText
        mark_texts = [row.get('markText', '').strip() for row in group_rows if row.get('markText', '').strip()]
        
        if mark_texts:
            chapter_names = []
            for chapter_uid in group_chapters:
                chapter_rows = chapters_dict[chapter_uid]
                chapter_name = chapter_rows[0].get('chapterName', f'章节{chapter_uid}') if chapter_rows else f'章节{chapter_uid}'
                chapter_names.append(chapter_name)
            
            print(f"\n处理组（章节 {group_chapters[0]}-{group_chapters[-1]}）: {', '.join(chapter_names)}（{len(mark_texts)} 条笔记）...")
            concepts = extractor.extract_concepts(mark_texts, domain)
            
            if concepts:
                print(f"  提取到 {len(concepts)} 个概念: {', '.join(concepts[:5])}{'...' if len(concepts) > 5 else ''}")
                all_concepts.extend(concepts)
            time.sleep(0.5)  # 避免请求过快
        
        # 移动到下一组（从最后一个已处理的章节的下一个开始）
        i = j
    
    print(f"\n共提取到 {len(all_concepts)} 个概念词（含重复）")
    
    # 第二步：去重
    print("\n" + "=" * 60)
    print("第二步：去重（概念和形式）")
    print("=" * 60)
    
    deduplicated_concepts = extractor.deduplicate_concepts(all_concepts)
    print(f"去重后剩余 {len(deduplicated_concepts)} 个概念")
    
    # 第三步：为每个概念生成详细信息
    print("\n" + "=" * 60)
    print("第三步：生成概念详细信息")
    print("=" * 60)
    
    concept_results = []
    
    for idx, concept in enumerate(deduplicated_concepts, 1):
        print(f"\n[{idx}/{len(deduplicated_concepts)}] 处理概念: {concept}")
        
        # 获取子分类
        print(f"  获取子分类...")
        category = extractor.get_concept_category(concept, domain)
        print(f"  子分类: {category}")
        time.sleep(0.3)
        
        # 找到相关句子
        source_sentences = extractor.find_sentences_with_concept(rows, concept)
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
        
        concept_results.append({
            'concept': concept,
            'domain': domain,
            'category': category,
            'source': book_title,
            'sentences': sentences_html,
            'short_definition': short_def,
            'definition': html_definition
        })
    
    # 关闭客户端
    extractor.close()
    
    # 保存到 CSV
    if output_file is None:
        script_dir = Path(__file__).parent  # llm/scripts
        output_dir = script_dir.parent / "output" / "concepts"  # llm/output/concepts
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f"{book_id}_concepts.csv"
    else:
        output_file = Path(output_file)
        output_file.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"\n正在保存到: {output_file}")
    
    fieldnames = ['concept', 'domain', 'category', 'source', 'sentences', 'short_definition', 'definition']
    
    try:
        with open(output_file, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for result in concept_results:
                writer.writerow(result)
        
        print(f"✓ 成功保存 {len(concept_results)} 个概念到 {output_file}")
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
  python extract_concepts.py --title "书名"
        """
    )
    
    # 书名和 bookID 二选一
    book_group = parser.add_mutually_exclusive_group(required=True)
    book_group.add_argument('--title', '--book-title', dest='book_title', type=str,
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
        api_key=api_key
    )


if __name__ == "__main__":
    main()

