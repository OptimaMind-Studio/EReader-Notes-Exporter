#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MarkNotes 生成工具
从笔记 CSV 文件中读取 reviewContent，使用 Gemini API 生成 HTML 格式的整理和总结
"""

import sys
import os
import csv
import time
import argparse
import subprocess
from pathlib import Path
from typing import Optional, List, Dict
from datetime import datetime
from google import genai

# 导入 prompt 模板
# 先添加路径，确保能找到 prompts 模块
script_dir = Path(__file__).parent  # llm/scripts
if str(script_dir) not in sys.path:
    sys.path.insert(0, str(script_dir))

# 尝试多种导入方式
GENERATE_MARKNOTE_HTML_PROMPT_TEMPLATE = None

try:
    # 从项目根目录运行时
    from llm.prompts import GENERATE_MARKNOTE_HTML_PROMPT_TEMPLATE
except ImportError:
    try:
        # 从 llm/scripts 目录运行时
        from prompts import GENERATE_MARKNOTE_HTML_PROMPT_TEMPLATE
    except ImportError:
        # 如果还是失败，使用 importlib 直接加载模块
        import importlib.util
        prompts_file = script_dir / "prompts.py"
        if prompts_file.exists():
            spec = importlib.util.spec_from_file_location("prompts", prompts_file)
            prompts_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(prompts_module)
            GENERATE_MARKNOTE_HTML_PROMPT_TEMPLATE = getattr(prompts_module, 'GENERATE_MARKNOTE_HTML_PROMPT_TEMPLATE', None)
        else:
            raise ImportError(f"无法找到 prompts.py 文件: {prompts_file}")

# 验证导入是否成功
if GENERATE_MARKNOTE_HTML_PROMPT_TEMPLATE is None:
    raise ImportError("无法导入 GENERATE_MARKNOTE_HTML_PROMPT_TEMPLATE，请确保 prompts.py 中包含此模板")


class MarkNoteGenerator:
    """使用 Gemini API 生成 MarkNote HTML"""
    
    def __init__(self, api_key: Optional[str] = None, max_retries: int = 3):
        """
        初始化 Gemini API 客户端
        
        Args:
            api_key: Gemini API 密钥，如果为 None 则从环境变量读取
            max_retries: 最大重试次数
        """
        if api_key is None:
            api_key = os.environ.get('GOOGLE_API_KEY') or os.environ.get('GEMINI_API_KEY')
        
        if not api_key:
            raise ValueError(
                "请提供 Gemini API 密钥。可以通过以下方式：\n"
                "1. 作为参数传入：MarkNoteGenerator(api_key='your_key')\n"
                "2. 设置环境变量：export GEMINI_API_KEY='your_api_key' 或 export GOOGLE_API_KEY='your_api_key'"
            )
        
        self.client = genai.Client(api_key=api_key)
        self.max_retries = max_retries
    
    def generate_html(self, review_content: str) -> str:
        """
        根据 reviewContent 生成 HTML 格式的整理和总结
        
        Args:
            review_content: 点评内容
        
        Returns:
            HTML 格式的内容
        """
        prompt = GENERATE_MARKNOTE_HTML_PROMPT_TEMPLATE.replace("{{review_content}}", review_content)
        
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
                    html_content = "<p>无法生成内容</p>"
                
                # 清理可能的 markdown 代码块标记和引号
                html_content = html_content.strip()
                html_content = html_content.replace('```html', '').replace('```', '')
                html_content = html_content.strip()
                # 移除前后引号（如果存在）
                if html_content.startswith('"') and html_content.endswith('"'):
                    html_content = html_content[1:-1]
                if html_content.startswith("'") and html_content.endswith("'"):
                    html_content = html_content[1:-1]
                
                html_content = html_content.strip()
                
                if html_content:
                    return html_content
                else:
                    if attempt < self.max_retries:
                        print(f"  ⚠️  返回内容为空（第 {attempt + 1} 次尝试），重试...")
                        continue
                    else:
                        return "<p>无法生成内容</p>"
                
            except Exception as e:
                last_exception = e
                error_msg = str(e).lower()
                
                # 某些错误不应该重试（如认证错误、参数错误）
                if any(keyword in error_msg for keyword in ['auth', 'permission', 'invalid', 'not found', '404']):
                    print(f"  ⚠️  生成 HTML 时出错（不可重试）: {e}")
                    return f"<p>生成内容时出错: {str(e)}</p>"
                
                # 如果是最后一次尝试，返回错误信息
                if attempt == self.max_retries:
                    break
                
                # 打印重试信息
                print(f"  ⚠️  生成 HTML 失败（第 {attempt + 1} 次尝试）: {e}，重试...")
                time.sleep(1)  # 重试前等待
        
        # 所有重试都失败，返回错误信息
        print(f"  ⚠️  生成 HTML 失败（重试 {self.max_retries} 次后）: {last_exception}")
        return f"<p>生成内容时出错: {str(last_exception)}</p>"
    
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
    处理 CSV 文件，为 reviewContent 生成 HTML
    
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
            print(f"\n✓ 数据已更新，继续处理 MarkNotes...\n")
    
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
    
    print(f"共读取 {len(rows)} 行数据\n")
    
    # 3. 确定输出文件路径
    if output_file is None:
        script_dir = Path(__file__).parent  # llm/scripts
        output_dir = script_dir.parent / "output" / "marknotes"  # llm/output/marknotes
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file_path = output_dir / f"{book_id}_marknotes.csv"
    else:
        output_file_path = Path(output_file)
        output_file_path.parent.mkdir(parents=True, exist_ok=True)
    
    # 4. 读取已存在的 marknotes CSV（如果存在）
    existing_marknotes = {}
    if output_file_path.exists():
        print(f"检测到已存在的 marknotes 文件: {output_file_path}")
        try:
            with open(output_file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # 使用 bookId + reviewId 作为唯一标识
                    note_book_id = row.get('bookId', '').strip()
                    note_review_id = row.get('reviewId', '').strip()
                    if note_book_id and note_review_id:
                        unique_key = f"{note_book_id}_{note_review_id}"
                        existing_marknotes[unique_key] = row
            print(f"  已加载 {len(existing_marknotes)} 条已有记录")
        except Exception as e:
            print(f"  ⚠️  读取已有 marknotes 文件失败: {e}")
    
    # 5. 初始化生成器
    generator = MarkNoteGenerator(api_key=api_key, max_retries=max_retries)
    
    # 6. 处理每一行数据
    print("=" * 60)
    print("开始处理 reviewContent，生成 HTML")
    print("=" * 60)
    
    # 获取原始 CSV 的所有列名
    if rows:
        original_columns = list(rows[0].keys())
    else:
        print("错误：没有数据行")
        generator.close()
        return
    
    # 添加新列 reviewContentHTML
    output_columns = original_columns + ['reviewContentHTML']
    
    processed_rows = []
    total_count = len(rows)
    processed_count = 0
    skipped_count = 0
    existing_count = 0
    
    for idx, row in enumerate(rows, 1):
        review_content = row.get('reviewContent', '').strip()
        note_book_id = row.get('bookId', '').strip()
        note_review_id = row.get('reviewId', '').strip()
        
        # 构建唯一标识
        unique_key = f"{note_book_id}_{note_review_id}" if (note_book_id and note_review_id) else None
        
        # 复制原始行数据
        new_row = row.copy()
        
        # 检查是否已存在
        if unique_key and unique_key in existing_marknotes:
            # 已存在，使用已有数据
            existing_row = existing_marknotes[unique_key]
            new_row['reviewContentHTML'] = existing_row.get('reviewContentHTML', '')
            processed_rows.append(new_row)
            existing_count += 1
            continue
        
        # 只有 reviewContent 字数大于 100 的才生成 HTML
        if len(review_content) > 100:
            print(f"\n[{idx}/{total_count}] 处理 reviewContent（{len(review_content)} 字）...")
            html_content = generator.generate_html(review_content)
            new_row['reviewContentHTML'] = html_content
            processed_rows.append(new_row)
            processed_count += 1
            time.sleep(0.3)  # 避免请求过快
        else:
            # 字数不足 100，不添加到输出（跳过）
            skipped_count += 1
    
    # 7. 合并已存在的记录和新增的记录
    # processed_rows 已经包含了新增的记录和从 existing_marknotes 中恢复的记录
    # 但还需要确保所有已存在的记录都被包含（即使它们在本次 notes CSV 中不存在）
    all_rows_dict = {}
    
    # 先添加本次处理的所有记录
    for row in processed_rows:
        note_book_id = row.get('bookId', '').strip()
        note_review_id = row.get('reviewId', '').strip()
        if note_book_id and note_review_id:
            unique_key = f"{note_book_id}_{note_review_id}"
            all_rows_dict[unique_key] = row
    
    # 再添加已存在但本次 notes CSV 中没有的记录（保留它们）
    for unique_key, existing_row in existing_marknotes.items():
        if unique_key not in all_rows_dict:
            # 这条记录在已有 marknotes 中，但不在本次 notes CSV 中，保留它
            all_rows_dict[unique_key] = existing_row
    
    # 8. 过滤掉 reviewContentHTML 为空的记录（只保留生成了 HTML 的记录）
    rows_with_html = [row for row in all_rows_dict.values() if row.get('reviewContentHTML', '').strip()]
    
    # 9. 保存到 CSV
    print(f"\n{'='*60}")
    print(f"处理完成")
    print(f"{'='*60}")
    print(f"总计: {total_count} 条记录（从 notes CSV）")
    print(f"  - 新增生成 HTML: {processed_count} 条（reviewContent > 100 字，调用 LLM）")
    print(f"  - 使用已有数据: {existing_count} 条（已存在于 marknotes CSV，跳过 LLM）")
    print(f"  - 跳过: {skipped_count} 条（reviewContent <= 100 字，不输出到 CSV）")
    print(f"  - 保留已有记录: {len(existing_marknotes) - existing_count} 条（在 marknotes CSV 中但不在本次 notes CSV 中）")
    
    if not rows_with_html:
        print(f"\n⚠️  没有符合条件的记录（reviewContent > 100 字），不生成 CSV 文件")
        generator.close()
        return
    
    print(f"\n正在保存到: {output_file_path}")
    
    try:
        with open(output_file_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=output_columns)
            writer.writeheader()
            # 按 bookId 和 reviewId 排序，确保输出顺序一致
            sorted_rows = sorted(rows_with_html, key=lambda x: (
                x.get('bookId', ''),
                x.get('reviewId', '')
            ))
            for row in sorted_rows:
                writer.writerow(row)
        
        print(f"✓ 成功保存 {len(rows_with_html)} 条记录到 {output_file_path}")
    except Exception as e:
        print(f"✗ 保存文件时出错: {e}")
    
    # 关闭客户端
    generator.close()


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='MarkNotes 生成工具：从笔记 CSV 文件中读取 reviewContent，使用 Gemini API 生成 HTML 格式的整理和总结',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  # 使用 bookID
  python generate_marknotes.py --book-id 42568673
  python generate_marknotes.py --book-id 42568673 --output llm/output/marknotes/book_marknotes.csv
  
  # 使用书名
  python generate_marknotes.py --book-name "效率脑科学"
  
  # 先 fetch 数据再处理
  python generate_marknotes.py --book-id 42568673 --fetch
  python generate_marknotes.py --book-name "效率脑科学" --fetch
        """
    )
    
    # 书名和 bookID 二选一
    book_group = parser.add_mutually_exclusive_group(required=True)
    book_group.add_argument('--book-name', '--book-title', dest='book_title', type=str,
                           help='书籍名称')
    book_group.add_argument('--book-id', '--id', dest='book_id', type=str,
                           help='书籍ID')
    
    parser.add_argument('--output', '--output-file', dest='output_file', type=str, default=None,
                       help='输出的 MarkNotes CSV 文件路径（可选，默认自动生成到 llm/output/marknotes/）')
    parser.add_argument('--api-key', type=str,
                       help='Gemini API 密钥（可选，优先从环境变量 GEMINI_API_KEY 或 GOOGLE_API_KEY 读取）')
    parser.add_argument('--max-retries', type=int, default=3,
                       help='最大重试次数（默认: 3）')
    parser.add_argument('--fetch', '--refresh-data', dest='fetch_data', action='store_true',
                       help='在处理之前，先重新 fetch 笔记数据（调用 wereader/fetch.py）')
    
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
        max_retries=args.max_retries,
        fetch_data=args.fetch_data
    )


if __name__ == "__main__":
    main()
