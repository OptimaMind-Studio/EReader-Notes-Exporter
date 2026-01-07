#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WeRead Data Pipeline Main Script
Sequentially executes all data fetching and merging scripts
"""

import subprocess
import sys
import os
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
    # Get script directory
    script_dir = Path(__file__).parent
    scripts_dir = script_dir / "scripts"
    
    # Get book ID filter (optional)
    filter_book_id = None
    if len(sys.argv) > 1:
        filter_book_id = sys.argv[1]
    
    print("="*60)
    print("WeRead Data Pipeline")
    print("="*60)
    if filter_book_id:
        print(f"\nFiltering to book ID: {filter_book_id}")
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
    # fetch_books.py: [cookie] [book_id]
    # We need to explicitly pass cookie file path so book_id can be passed correctly
    fetch_books_args = [str(default_cookie_file)]
    if filter_book_id:
        fetch_books_args.append(filter_book_id)
    
    success = run_script(
        scripts_dir / "fetch_books.py",
        "Step 1: Fetch books list",
        *fetch_books_args
    )
    if not success:
        print("\nPipeline stopped: Failed to fetch books list.")
        sys.exit(1)
    
    # Step 2: Fetch bookmarks
    # fetch_bookmarks.py: [cookie] [csv_file] [output_dir] [book_id]
    # We need to pass all parameters to reach book_id position
    fetch_bookmarks_args = []
    if filter_book_id:
        # Pass cookie file, csv_file, output_dir, and book_id
        fetch_bookmarks_args = [
            str(default_cookie_file),
            str(default_csv_file),
            str(default_bookmarks_dir),
            filter_book_id
        ]
    
    success = run_script(
        scripts_dir / "fetch_bookmarks.py",
        "Step 2: Fetch bookmarks",
        *fetch_bookmarks_args
    )
    if not success:
        print("\nWarning: Failed to fetch bookmarks. Continuing with next step...")
    
    # Step 3: Fetch reviews
    # fetch_reviews.py: [cookie] [csv_file] [output_dir] [book_id]
    fetch_reviews_args = []
    if filter_book_id:
        fetch_reviews_args = [
            str(default_cookie_file),
            str(default_csv_file),
            str(default_reviews_dir),
            filter_book_id
        ]
    
    success = run_script(
        scripts_dir / "fetch_reviews.py",
        "Step 3: Fetch reviews",
        *fetch_reviews_args
    )
    if not success:
        print("\nWarning: Failed to fetch reviews. Continuing with next step...")
    
    # Step 4: Merge notes
    # merge_notes.py: [csv_file] [bookmarks_dir] [reviews_dir] [output_dir] [book_id]
    merge_notes_args = []
    if filter_book_id:
        merge_notes_args = [
            str(default_csv_file),
            str(default_bookmarks_dir),
            str(default_reviews_dir),
            str(default_output_dir),
            filter_book_id
        ]
    
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
    if filter_book_id:
        print(f"Processed book ID: {filter_book_id}")
    else:
        print("Processed all books")
    print("\nCheck the output directories for results:")
    print(f"  - Books CSV: {script_dir / 'output' / 'fetch_notebooks_output.csv'}")
    print(f"  - Bookmarks: {script_dir / 'output' / 'bookmarks'}")
    print(f"  - Reviews: {script_dir / 'output' / 'reviews'}")
    print(f"  - Merged Notes: {script_dir / 'output' / 'notes'}")


if __name__ == "__main__":
    main()

