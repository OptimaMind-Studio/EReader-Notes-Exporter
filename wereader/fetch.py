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
from pathlib import Path


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
  python main.py
  python main.py --book-id 3300064831
        """
    )
    
    parser.add_argument('--book-id', '--id', dest='book_id', type=str, default=None,
                       help='书籍ID（可选，如果提供则只处理该书籍）')
    
    args = parser.parse_args()
    
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

