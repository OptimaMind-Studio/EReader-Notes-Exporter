#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WeRead Data Pipeline Main Script
Sequentially executes all data fetching and merging scripts
"""

import subprocess
import sys
import os
import argparse
import csv
from pathlib import Path
from typing import Optional


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


def run_script(script_path: str, description: str, *args) -> bool:
    """
    Run a Python script and return success status
    
    Args:
        script_path: Path to the script file
        description: Description of what the script does
        *args: Additional arguments to pass to the script
    
    Returns:
        True if script executed successfully, False otherwise
    """
    print("\n" + "="*60)
    print(f"Running: {description}")
    print("="*60)
    
    script_file = Path(script_path)
    if not script_file.exists():
        print(f"Error: Script not found: {script_path}")
        return False
    
    # Build command
    cmd = [sys.executable, str(script_file)] + list(args)
    
    try:
        result = subprocess.run(cmd, check=False, capture_output=False)
        if result.returncode == 0:
            print(f"\n✓ Successfully completed: {description}")
            return True
        else:
            print(f"\n✗ Failed: {description} (exit code: {result.returncode})")
            return False
    except Exception as e:
        print(f"\n✗ Error running {description}: {e}")
        return False


def main():
    """Main function to run all scripts in sequence"""
    parser = argparse.ArgumentParser(
        description='WeRead Data Pipeline: 依次执行所有数据获取和合并脚本',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python wereader/fetch.py
  python wereader/fetch.py --book-id 3300064831
  python wereader/fetch.py --book-name "极简央行课"
        """
    )
    
    parser.add_argument('--book-id', '--id', dest='book_id', type=str, default=None,
                       help='书籍ID（可选，如果提供则只处理该书籍）')
    parser.add_argument('--book-name', '--title', '--name', dest='book_name', type=str, default=None,
                       help='书名（可选，如果提供则只处理该书籍，需要先运行一次 fetch_books.py 生成书籍列表）')
    
    args = parser.parse_args()
    
    # 如果提供了书名但没有提供 book_id，尝试从 CSV 文件中查找
    if args.book_name and not args.book_id:
        script_dir = Path(__file__).parent
        csv_file = script_dir / "output" / "fetch_notebooks_output.csv"
        
        if csv_file.exists():
            book_id = find_book_id_by_title(csv_file, args.book_name)
            if book_id:
                print(f"✓ 找到书名 '{args.book_name}' 对应的 bookId: {book_id}")
                args.book_id = book_id
            else:
                print(f"❌ 错误：未找到书名 '{args.book_name}' 对应的书籍")
                print(f"   请先运行 'python wereader/fetch.py' 生成书籍列表，或使用 --book-id 参数")
                sys.exit(1)
        else:
            print(f"❌ 错误：未找到书籍列表文件: {csv_file}")
            print(f"   请先运行 'python wereader/fetch.py' 生成书籍列表，或使用 --book-id 参数")
            sys.exit(1)
    
    # Get script directory
    script_dir = Path(__file__).parent
    scripts_dir = script_dir / "scripts"
    
    print("="*60)
    print("WeRead Data Pipeline")
    print("="*60)
    if args.book_id:
        print(f"\nFiltering to book ID: {args.book_id}")
    else:
        print("\nProcessing all books")
    print("\nThis script will execute the following steps:")
    print("  1. Fetch books list (fetch_books.py)")
    print("  2. Fetch bookmarks (fetch_bookmarks.py)")
    print("  3. Fetch reviews (fetch_reviews.py)")
    print("  4. Merge bookmarks and reviews (merge_notes.py)")
    print("\nStarting pipeline...")
    
    # Get default paths for passing to scripts
    default_cookie_file = script_dir / "cookies.txt"
    default_csv_file = script_dir / "output" / "fetch_notebooks_output.csv"
    default_bookmarks_dir = script_dir / "output" / "bookmarks"
    default_reviews_dir = script_dir / "output" / "reviews"
    default_output_dir = script_dir / "output" / "notes"
    
    # Step 1: Fetch books
    fetch_books_args = ['--cookie', str(default_cookie_file)]
    if args.book_id:
        fetch_books_args.extend(['--book-id', args.book_id])
    
    success = run_script(
        scripts_dir / "fetch_books.py",
        "Step 1: Fetch books list",
        *fetch_books_args
    )
    if not success:
        print("\nPipeline stopped: Failed to fetch books list.")
        sys.exit(1)
    
    # Step 2: Fetch bookmarks
    fetch_bookmarks_args = [
        '--cookie', str(default_cookie_file),
        '--csv-file', str(default_csv_file),
        '--output-dir', str(default_bookmarks_dir)
    ]
    if args.book_id:
        fetch_bookmarks_args.extend(['--book-id', args.book_id])
    
    success = run_script(
        scripts_dir / "fetch_bookmarks.py",
        "Step 2: Fetch bookmarks",
        *fetch_bookmarks_args
    )
    if not success:
        print("\nWarning: Failed to fetch bookmarks. Continuing with next step...")
    
    # Step 3: Fetch reviews
    fetch_reviews_args = [
        '--cookie', str(default_cookie_file),
        '--csv-file', str(default_csv_file),
        '--output-dir', str(default_reviews_dir)
    ]
    if args.book_id:
        fetch_reviews_args.extend(['--book-id', args.book_id])
    
    success = run_script(
        scripts_dir / "fetch_reviews.py",
        "Step 3: Fetch reviews",
        *fetch_reviews_args
    )
    if not success:
        print("\nWarning: Failed to fetch reviews. Continuing with next step...")
    
    # Step 4: Merge notes
    merge_notes_args = [
        '--csv-file', str(default_csv_file),
        '--bookmarks-dir', str(default_bookmarks_dir),
        '--reviews-dir', str(default_reviews_dir),
        '--output-dir', str(default_output_dir)
    ]
    if args.book_id:
        merge_notes_args.extend(['--book-id', args.book_id])
    
    success = run_script(
        scripts_dir / "merge_notes.py",
        "Step 4: Merge bookmarks and reviews",
        *merge_notes_args
    )
    if not success:
        print("\nWarning: Failed to merge notes.")
    
    # Final summary
    print("\n" + "="*60)
    print("Pipeline Execution Complete")
    print("="*60)
    print("\nAll scripts have been executed.")
    if args.book_id:
        print(f"Processed book ID: {args.book_id}")
    else:
        print("Processed all books")
    print("\nCheck the output directories for results:")
    print(f"  - Books CSV: {script_dir / 'output' / 'fetch_notebooks_output.csv'}")
    print(f"  - Bookmarks: {script_dir / 'output' / 'bookmarks'}")
    print(f"  - Reviews: {script_dir / 'output' / 'reviews'}")
    print(f"  - Merged Notes: {script_dir / 'output' / 'notes'}")


if __name__ == "__main__":
    main()

