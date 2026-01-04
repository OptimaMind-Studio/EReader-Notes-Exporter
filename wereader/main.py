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
    
    print("="*60)
    print("WeRead Data Pipeline")
    print("="*60)
    print("\nThis script will execute the following steps:")
    print("  1. Fetch books list (fetch_books.py)")
    print("  2. Fetch bookmarks for all books (fetch_bookmarks.py)")
    print("  3. Fetch reviews for all books (fetch_reviews.py)")
    print("  4. Merge bookmarks and reviews (merge_notes.py)")
    print("\nStarting pipeline...")
    
    # Step 1: Fetch books
    success = run_script(
        scripts_dir / "fetch_books.py",
        "Step 1: Fetch books list"
    )
    if not success:
        print("\nPipeline stopped: Failed to fetch books list.")
        sys.exit(1)
    
    # Step 2: Fetch bookmarks
    success = run_script(
        scripts_dir / "fetch_bookmarks.py",
        "Step 2: Fetch bookmarks"
    )
    if not success:
        print("\nWarning: Failed to fetch bookmarks. Continuing with next step...")
    
    # Step 3: Fetch reviews
    success = run_script(
        scripts_dir / "fetch_reviews.py",
        "Step 3: Fetch reviews"
    )
    if not success:
        print("\nWarning: Failed to fetch reviews. Continuing with next step...")
    
    # Step 4: Merge notes
    success = run_script(
        scripts_dir / "merge_notes.py",
        "Step 4: Merge bookmarks and reviews"
    )
    if not success:
        print("\nWarning: Failed to merge notes.")
    
    # Final summary
    print("\n" + "="*60)
    print("Pipeline Execution Complete")
    print("="*60)
    print("\nAll scripts have been executed.")
    print("Check the output directories for results:")
    print(f"  - Books CSV: {script_dir / 'output' / 'fetch_notebooks_output.csv'}")
    print(f"  - Bookmarks: {script_dir / 'output' / 'bookmarks'}")
    print(f"  - Reviews: {script_dir / 'output' / 'reviews'}")
    print(f"  - Merged Notes: {script_dir / 'output' / 'notes'}")


if __name__ == "__main__":
    main()

