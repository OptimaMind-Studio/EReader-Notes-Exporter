#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
学习指南生成工具
根据书名和章节名，从笔记中提取相关内容，使用 Gemini API 生成逐句解释
"""

import sys
import os
import csv
import time
import argparse
import asyncio
import re
from pathlib import Path
from typing import Optional, List, Dict
from datetime import datetime
from google import genai

# 导入 prompt 模板
try:
    # 从项目根目录运行时
    from llm.prompts import GUIDEBOOK_EXPLANATION_PROMPT_TEMPLATE
except ImportError:
    # 从 llm 目录运行时
    from prompts import GUIDEBOOK_EXPLANATION_PROMPT_TEMPLATE


class GuidebookGenerator:
    """使用 Gemini API 生成学习指南"""
    
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
                "1. 作为参数传入：GuidebookGenerator(api_key='your_key')\n"
                "2. 设置环境变量：export GEMINI_API_KEY='your_api_key' 或 export GOOGLE_API_KEY='your_api_key'"
            )
        
        self.client = genai.Client(api_key=api_key)
        self.api_key = api_key
    
    def generate_explanation(self, mark_text: str, domain: str, title: str) -> str:
        """
        生成对划线文本的解释（同步版本，保留用于兼容）
        
        Args:
            mark_text: 划线文本
            domain: 领域
            title: 书名
        
        Returns:
            HTML 格式的解释文本
        """
        prompt = GUIDEBOOK_EXPLANATION_PROMPT_TEMPLATE.replace("{{domain}}", domain)
        prompt = prompt.replace("{{title}}", title)
        prompt = prompt.replace("{{mark_text}}", mark_text)
        
        try:
            response = self.client.models.generate_content(
                model='gemini-2.0-flash-001',
                contents=prompt,
            )
            
            if hasattr(response, 'text'):
                explanation = response.text
            elif hasattr(response, 'candidates') and len(response.candidates) > 0:
                explanation = response.candidates[0].content.parts[0].text
            else:
                explanation = str(response)
            
            explanation = explanation.strip()
            
            # 清理可能的 markdown 代码块标记和引号
            # 移除 markdown 代码块标记（```html, ```, 等）
            explanation = re.sub(r'^```[a-z]*\n?', '', explanation, flags=re.MULTILINE)
            explanation = re.sub(r'\n?```$', '', explanation, flags=re.MULTILINE)
            # 移除前后引号（如果存在）
            explanation = explanation.strip()
            if explanation.startswith('"') and explanation.endswith('"'):
                explanation = explanation[1:-1]
            if explanation.startswith("'") and explanation.endswith("'"):
                explanation = explanation[1:-1]
            
            return explanation.strip()
        
        except Exception as e:
            return f"生成解释时出错：{str(e)}"
    
    async def generate_explanation_async(self, mark_text: str, domain: str, title: str, index: int, total: int) -> tuple[int, str]:
        """
        异步生成对划线文本的解释
        
        Args:
            mark_text: 划线文本
            domain: 领域
            title: 书名
            index: 当前索引（用于日志）
            total: 总数（用于日志）
        
        Returns:
            (index, HTML格式的解释文本) 元组
        """
        prompt = GUIDEBOOK_EXPLANATION_PROMPT_TEMPLATE.replace("{{domain}}", domain)
        prompt = prompt.replace("{{title}}", title)
        prompt = prompt.replace("{{mark_text}}", mark_text)
        
        # 打印开始日志
        start_time = time.time()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] [{index}/{total}] llm call-start: {mark_text[:50]}...")
        
        try:
            # 在线程池中运行同步调用
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.models.generate_content(
                    model='gemini-2.0-flash-001',
                    contents=prompt,
                )
            )
            
            if hasattr(response, 'text'):
                explanation = response.text
            elif hasattr(response, 'candidates') and len(response.candidates) > 0:
                explanation = response.candidates[0].content.parts[0].text
            else:
                explanation = str(response)
            
            explanation = explanation.strip()
            
            # 清理可能的 markdown 代码块标记和引号
            # 移除 markdown 代码块标记（```html, ```, 等）
            explanation = re.sub(r'^```[a-z]*\n?', '', explanation, flags=re.MULTILINE)
            explanation = re.sub(r'\n?```$', '', explanation, flags=re.MULTILINE)
            # 移除前后引号（如果存在）
            explanation = explanation.strip()
            if explanation.startswith('"') and explanation.endswith('"'):
                explanation = explanation[1:-1]
            if explanation.startswith("'") and explanation.endswith("'"):
                explanation = explanation[1:-1]
            explanation = explanation.strip()
            
            # 打印结束日志
            end_time = time.time()
            elapsed = end_time - start_time
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{timestamp}] [{index}/{total}] llm call-end: 完成 (耗时 {elapsed:.2f}秒)")
            
            return (index, explanation)
        
        except Exception as e:
            # 打印错误日志
            end_time = time.time()
            elapsed = end_time - start_time
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            error_msg = f"生成解释时出错：{str(e)}"
            print(f"[{timestamp}] [{index}/{total}] llm call-end: 错误 (耗时 {elapsed:.2f}秒) - {error_msg}")
            return (index, error_msg)
    
    def close(self):
        """关闭客户端"""
        if hasattr(self, 'client'):
            try:
                self.client.close()
            except:
                pass


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


def read_notes_csv(csv_file: str, chapter_name: Optional[str] = None) -> List[Dict[str, str]]:
    """
    读取笔记 CSV 文件，并根据章节名过滤（如果提供）
    
    Args:
        csv_file: CSV 文件路径
        chapter_name: 章节名（可选，如果为 None 则返回所有笔记）
    
    Returns:
        过滤后的笔记列表
    """
    notes = []
    try:
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # 如果提供了章节名，则过滤；否则返回所有笔记
                if chapter_name:
                    chapter = row.get('chapterName', '').strip()
                    if chapter != chapter_name:
                        continue
                
                # 只保留有 markText 和 bookmarkId 的行
                if row.get('markText', '').strip() and row.get('bookmarkId', '').strip():
                    notes.append(row)
        return notes
    except Exception as e:
        print(f"错误：读取笔记 CSV 文件失败: {e}")
        return []


async def process_guidebook_async(book_id: Optional[str] = None, book_title: Optional[str] = None, chapter_name: Optional[str] = None, api_key: Optional[str] = None, concurrency: int = 10):
    """
    处理学习指南生成流程
    
    Args:
        book_id: 书籍ID（与 book_title 二选一）
        book_title: 书名（与 book_id 二选一）
        chapter_name: 章节名（可选，如果为 None 则处理整本书）
        api_key: Gemini API 密钥
    """
    # 获取脚本所在目录
    script_dir = Path(__file__).parent  # llm/scripts
    project_root = script_dir.parent.parent  # 项目根目录
    
    # 默认路径
    notebooks_csv = project_root / "wereader" / "output" / "fetch_notebooks_output.csv"
    notes_dir = project_root / "wereader" / "output" / "notes"
    output_dir = script_dir.parent / "output" / "guidebook"  # llm/output/guidebook
    
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
    
    # 2. 读取笔记 CSV
    notes_csv = notes_dir / f"{book_id}.csv"
    
    if not notes_csv.exists():
        print(f"错误：笔记文件不存在: {notes_csv}")
        return
    
    print(f"正在读取笔记文件: {notes_csv}")
    notes = read_notes_csv(str(notes_csv), chapter_name)
    
    if not notes:
        if chapter_name:
            print(f"错误：未找到章节 '{chapter_name}' 的笔记")
        else:
            print(f"错误：未找到书籍的笔记")
        return
    
    print(f"找到 {len(notes)} 条笔记\n")
    
    # 获取书籍信息
    domain = book_info.get('categories', '').strip() if book_info else ''
    title = book_info.get('title', book_title_display).strip() if book_info else book_title_display
    
    print(f"领域: {domain}")
    print(f"书名: {title}")
    if chapter_name:
        print(f"章节: {chapter_name}")
    else:
        print(f"处理范围: 整本书")
    print()
    
    # 3. 初始化生成器
    generator = GuidebookGenerator(api_key=api_key)
    
    # 4. 准备需要处理的笔记
    print("=" * 60)
    print(f"开始生成解释（并行度: {concurrency}）...")
    print("=" * 60)
    
    # 4.1 获取输入 notes 中的所有 bookmarkId 集合（用于验证输出 CSV）
    input_bookmark_ids = set()
    for note in notes:
        bookmark_id = note.get('bookmarkId', '').strip()
        if bookmark_id:
            input_bookmark_ids.add(bookmark_id)
    
    # 4.2 检查输出文件是否已存在，如果存在则读取已处理的 bookmarkId，并清理无效记录
    output_file = None
    existing_bookmark_ids = set()
    
    if chapter_name:
        safe_chapter_name = chapter_name.replace('/', '_').replace('\\', '_')
        output_file = output_dir / f"{book_id}_{safe_chapter_name}_guidebook.csv"
    else:
        output_file = output_dir / f"{book_id}_all_chapters_guidebook.csv"
    
    if output_file.exists():
        print(f"\n检测到已存在的输出文件: {output_file}")
        print("正在读取已处理的 bookmarkId...")
        
        # 读取输出 CSV，同时检查并清理无效记录
        valid_output_rows = []
        deleted_count = 0
        
        try:
            with open(output_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                columns = reader.fieldnames
                
                for row in reader:
                    bookmark_id = row.get('bookmarkId', '').strip()
                    if bookmark_id:
                        # 检查该 bookmarkId 是否在输入 CSV 中存在
                        if bookmark_id in input_bookmark_ids:
                            existing_bookmark_ids.add(bookmark_id)
                            valid_output_rows.append(row)
                        else:
                            deleted_count += 1
            
            # 如果有记录被删除，重新写入文件
            if deleted_count > 0:
                print(f"发现 {deleted_count} 条无效记录（bookmarkId 不在输入 CSV 中），正在清理...")
                with open(output_file, 'w', encoding='utf-8', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=columns, extrasaction='ignore')
                    writer.writeheader()
                    for row in valid_output_rows:
                        writer.writerow(row)
                print(f"✓ 已清理 {deleted_count} 条无效记录，保留 {len(valid_output_rows)} 条有效记录")
            else:
                print(f"已找到 {len(existing_bookmark_ids)} 条已处理的记录，无需清理")
                
        except Exception as e:
            print(f"⚠️  读取已存在文件时出错: {e}，将重新处理所有记录")
            existing_bookmark_ids = set()
    
    # 4.2 过滤出有效的笔记（有 markText 和 bookmarkId），并排除已处理的
    valid_notes = []
    note_indices = []
    skipped_count = 0
    
    for idx, note in enumerate(notes, 1):
        mark_text = note.get('markText', '').strip()
        bookmark_id = note.get('bookmarkId', '').strip()
        
        if not mark_text or not bookmark_id:
            if not bookmark_id:
                print(f"[{idx}/{len(notes)}] 跳过（bookmarkId 为空）: {mark_text[:50] if mark_text else '无markText'}...")
            continue
        
        # 检查是否已处理过
        if bookmark_id in existing_bookmark_ids:
            skipped_count += 1
            continue
        
        valid_notes.append(note)
        note_indices.append(idx)
    
    if skipped_count > 0:
        print(f"\n跳过 {skipped_count} 条已处理的记录")
    
    if not valid_notes:
        print("没有新的笔记需要处理")
        generator.close()
        return
    
    print(f"\n共 {len(valid_notes)} 条新笔记需要处理，开始异步处理...\n")
    
    # 5. 异步并发处理
    start_total_time = time.time()
    
    # 创建信号量控制并发数
    semaphore = asyncio.Semaphore(concurrency)
    
    async def process_with_semaphore(note, idx, total):
        async with semaphore:
            mark_text = note.get('markText', '').strip()
            return await generator.generate_explanation_async(mark_text, domain, title, idx, total)
    
    # 创建所有任务
    tasks = [
        process_with_semaphore(note, note_indices[i], len(valid_notes))
        for i, note in enumerate(valid_notes)
    ]
    
    # 执行所有任务
    results_data = await asyncio.gather(*tasks)
    
    end_total_time = time.time()
    total_elapsed = end_total_time - start_total_time
    
    # 6. 整理结果（按原始索引排序）
    results_data.sort(key=lambda x: x[0])  # 按索引排序
    
    results = []
    for (idx, explanation_html), note in zip(results_data, valid_notes):
        chapter_uid = note.get('chapterUid', '').strip()
        mark_text = note.get('markText', '').strip()
        bookmark_id = note.get('bookmarkId', '').strip()
        chapter_name_display = note.get('chapterName', '').strip() or (chapter_name if chapter_name else '')
        
        # 生成 CardName: guidebook_书名_章节名_bookmarkId
        card_name = f"guidebook_{title}_{chapter_name_display}_{bookmark_id}"
        
        results.append({
            'title': title,
            'categories': domain,
            'chapterName': chapter_name_display,
            'chapterUid': chapter_uid,
            'markText': mark_text,
            'markTextIndex': idx,
            'bookmarkId': bookmark_id,
            'CardName': card_name,
            'explanation': explanation_html
        })
    
    # 关闭客户端
    generator.close()
    
    # 打印总计用时
    print("\n" + "=" * 60)
    print(f"总计用时: {total_elapsed:.2f}秒")
    print(f"处理笔记数: {len(results)}")
    print(f"平均每条: {total_elapsed/len(results):.2f}秒" if results else "")
    print("=" * 60)
    
    # 5. 保存到 CSV
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # output_file 已在前面定义
    # 定义列名（使用英文，与输入 CSV 列名保持一致）
    columns = ['CardName', 'title', 'categories', 'chapterName', 'chapterUid', 'markText', 'markTextIndex', 'bookmarkId', 'explanation']
    
    # 判断是追加还是新建
    file_exists = output_file.exists()
    mode = 'a' if file_exists else 'w'
    
    if file_exists:
        print(f"\n正在追加 {len(results)} 条新记录到: {output_file}")
    else:
        print(f"\n正在保存 {len(results)} 条记录到: {output_file}")
    
    # 写入 CSV（追加模式或新建模式）
    with open(output_file, mode, encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction='ignore')
        
        # 如果是新建文件，写入表头
        if not file_exists:
            writer.writeheader()
        
        # 写入新结果
        for result in results:
            writer.writerow(result)
    
    if file_exists:
        print(f"\n✓ 已追加 {len(results)} 条新记录到 {output_file}")
    else:
        print(f"\n✓ 已保存 {len(results)} 条记录到 {output_file}")


def process_guidebook(book_id: Optional[str] = None, book_title: Optional[str] = None, chapter_name: Optional[str] = None, api_key: Optional[str] = None, concurrency: int = 10):
    """
    处理学习指南生成流程（同步包装器）
    
    Args:
        book_id: 书籍ID（与 book_title 二选一）
        book_title: 书名（与 book_id 二选一）
        chapter_name: 章节名（可选，如果为 None 则处理整本书）
        api_key: Gemini API 密钥
        concurrency: 并行度（默认10）
    """
    asyncio.run(process_guidebook_async(book_id, book_title, chapter_name, api_key, concurrency))


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='学习指南生成工具：根据书名或书籍ID，从笔记中提取相关内容，使用 Gemini API 生成逐句解释',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  # 使用书名和章节名
  python generate_guidebook.py --title "你一定要读的50部投资学经典" --chapter "前言"
  
  # 使用 bookID 和章节名
  python generate_guidebook.py --book-id 3300064831 --chapter "第一章"
  
  # 使用书名，处理整本书
  python generate_guidebook.py --title "效率脑科学：卓有成效地完成每一项工作"
  
  # 使用 bookID，处理整本书
  python generate_guidebook.py --book-id 3300064831
        """
    )
    
    # 书名和 bookID 二选一
    book_group = parser.add_mutually_exclusive_group(required=True)
    book_group.add_argument('--title', '--book-title', dest='book_title', type=str,
                           help='书籍名称')
    book_group.add_argument('--book-id', '--id', dest='book_id', type=str,
                           help='书籍ID')
    
    # 章节名可选
    parser.add_argument('--chapter', '--chapter-name', dest='chapter_name', type=str,
                       help='章节名称（可选，如果不提供则处理整本书）')
    
    # 并行度参数
    parser.add_argument('--concurrency', '--parallel', dest='concurrency', type=int, default=10,
                       help='并行度，同时进行的 LLM 调用数量（默认: 10）')
    
    # API key（可选，优先从环境变量读取）
    parser.add_argument('--api-key', type=str,
                       help='Gemini API 密钥（可选，优先从环境变量 GEMINI_API_KEY 或 GOOGLE_API_KEY 读取）')
    
    args = parser.parse_args()
    
    # 获取 API 密钥（优先从命令行参数，其次从环境变量）
    api_key = args.api_key or os.environ.get('GOOGLE_API_KEY') or os.environ.get('GEMINI_API_KEY')
    
    if not api_key:
        print("错误：请设置 GEMINI_API_KEY 或 GOOGLE_API_KEY 环境变量，或使用 --api-key 参数")
        sys.exit(1)
    
    try:
        process_guidebook(
            book_id=args.book_id,
            book_title=args.book_title,
            chapter_name=args.chapter_name,
            api_key=api_key,
            concurrency=args.concurrency
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

