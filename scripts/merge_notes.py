#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WeRead Notes Merger
Merges bookmarks and reviews into unified notes CSV files
"""

import csv
import sys
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from collections import defaultdict


def read_book_ids_from_csv(csv_file: str) -> List[Dict[str, str]]:
    """
    Read book IDs and metadata from CSV file
    
    Args:
        csv_file: Path to CSV file
    
    Returns:
        List of dicts with bookId, title, author, and categories
    """
    books = []
    
    try:
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                book_id = row.get('bookId', '').strip()
                if book_id:
                    books.append({
                        'bookId': book_id,
                        'title': row.get('title', '').strip(),
                        'author': row.get('author', '').strip(),
                        'categories': row.get('categories', '').strip()
                    })
        
        print(f"Successfully loaded {len(books)} book(s) from CSV file")
        return books
        
    except Exception as e:
        print(f"Error reading CSV file: {e}")
        return []


def read_bookmarks_csv(file_path: str) -> List[Dict[str, Any]]:
    """
    Read bookmarks from CSV file
    
    Args:
        file_path: Path to bookmarks CSV file
    
    Returns:
        List of bookmark dictionaries
    """
    if not os.path.exists(file_path):
        return []
    
    bookmarks = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                bookmarks.append(row)
        return bookmarks
    except Exception as e:
        print(f"  Error reading bookmarks file {file_path}: {e}")
        return []


def read_reviews_csv(file_path: str) -> List[Dict[str, Any]]:
    """
    Read reviews from CSV file
    
    Args:
        file_path: Path to reviews CSV file
    
    Returns:
        List of review dictionaries
    """
    if not os.path.exists(file_path):
        return []
    
    reviews = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                reviews.append(row)
        return reviews
    except Exception as e:
        print(f"  Error reading reviews file {file_path}: {e}")
        return []


def merge_notes(bookmarks: List[Dict], reviews: List[Dict], book_metadata: Dict[str, str]) -> List[Dict]:
    """
    Merge bookmarks and reviews into unified notes
    
    Args:
        bookmarks: List of bookmark dictionaries
        reviews: List of review dictionaries
        book_metadata: Dictionary with bookId, title, author, categories
    
    Returns:
        List of merged note dictionaries
    """
    # Extract all chapterUids and sort
    chapter_uids = set()
    
    for bookmark in bookmarks:
        chapter_uid = bookmark.get('chapterUid', '')
        if chapter_uid:
            try:
                chapter_uids.add(int(chapter_uid))
            except (ValueError, TypeError):
                pass
    
    for review in reviews:
        chapter_uid = review.get('chapterUid', '')
        if chapter_uid:
            try:
                chapter_uids.add(int(chapter_uid))
            except (ValueError, TypeError):
                pass
    
    sorted_chapter_uids = sorted(chapter_uids)
    
    merged_notes = []
    
    # Process each chapterUid
    for chapter_uid in sorted_chapter_uids:
        # Filter bookmarks for this chapterUid
        chapter_bookmarks = [
            bm for bm in bookmarks
            if str(bm.get('chapterUid', '')) == str(chapter_uid)
        ]
        
        # Filter reviews for this chapterUid
        chapter_reviews = [
            rv for rv in reviews
            if str(rv.get('chapterUid', '')) == str(chapter_uid)
        ]
        
        # Convert bookmarks to unified format
        for bm in chapter_bookmarks:
            note = {
                'bookId': book_metadata.get('bookId', ''),
                'title': book_metadata.get('title', ''),
                'author': book_metadata.get('author', ''),
                'categories': book_metadata.get('categories', ''),
                'bookmarkId': bm.get('bookmarkId', ''),
                'reviewId': '',
                'chapterName': bm.get('chapterName', ''),
                'chapterUid': str(chapter_uid),
                'markText': bm.get('markText', ''),
                'reviewContent': '',
                'createTime': bm.get('createTime', '')
            }
            merged_notes.append(note)
        
        # Convert reviews to unified format
        for rv in chapter_reviews:
            note = {
                'bookId': book_metadata.get('bookId', ''),
                'title': book_metadata.get('title', ''),
                'author': book_metadata.get('author', ''),
                'categories': book_metadata.get('categories', ''),
                'bookmarkId': '',
                'reviewId': rv.get('reviewId', ''),
                'chapterName': rv.get('chapterName', ''),
                'chapterUid': str(chapter_uid),
                'markText': rv.get('abstract', ''),
                'reviewContent': rv.get('content', ''),
                'createTime': rv.get('createTime', '')
            }
            merged_notes.append(note)
    
    # Sort all notes by createTime (ascending)
    merged_notes.sort(key=lambda x: int(x.get('createTime', 0)) if x.get('createTime') and str(x.get('createTime')).isdigit() else 0)
    
    # Deduplicate by markText: if two records have the same markText, keep the one with non-empty reviewContent
    seen_marktext = {}
    deduplicated_notes = []
    
    for note in merged_notes:
        mark_text = note.get('markText', '').strip()
        review_content = note.get('reviewContent', '').strip()
        
        if not mark_text:
            # Keep notes with empty markText (no deduplication needed)
            deduplicated_notes.append(note)
            continue
        
        if mark_text not in seen_marktext:
            # First occurrence of this markText
            seen_marktext[mark_text] = len(deduplicated_notes)
            deduplicated_notes.append(note)
        else:
            # Duplicate markText found
            existing_index = seen_marktext[mark_text]
            existing_note = deduplicated_notes[existing_index]
            existing_review_content = existing_note.get('reviewContent', '').strip()
            
            # Keep the one with non-empty reviewContent
            if review_content and not existing_review_content:
                # Replace existing with current (current has reviewContent)
                deduplicated_notes[existing_index] = note
            # If both have reviewContent or both don't, keep the existing one (first occurrence)
            # If current doesn't have reviewContent but existing does, keep existing
    
    # Re-sort after deduplication to maintain createTime order
    deduplicated_notes.sort(key=lambda x: int(x.get('createTime', 0)) if x.get('createTime') and str(x.get('createTime')).isdigit() else 0)
    
    return deduplicated_notes


def save_notes_to_csv(notes: List[Dict], book_id: str, output_dir: str) -> str:
    """
    Save merged notes to CSV file
    
    Args:
        notes: List of merged note dictionaries
        book_id: Book ID for filename
        output_dir: Output directory
    
    Returns:
        Path to saved file
    """
    # Use bookId for filename
    filename = f"{book_id}.csv"
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    file_path = output_path / filename
    
    # Define columns
    columns = ['bookId', 'title', 'author', 'categories', 'bookmarkId', 'reviewId', 
               'chapterName', 'chapterUid', 'markText', 'reviewContent', 'createTime']
    
    # Write CSV file
    with open(file_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction='ignore')
        writer.writeheader()
        
        for note in notes:
            row = {}
            for col in columns:
                value = note.get(col, '')
                if value is None:
                    row[col] = ''
                else:
                    row[col] = str(value)
            writer.writerow(row)
    
    return str(file_path)


def main():
    """Main function"""
    # Default paths (parent directory, same level as scripts folder)
    script_dir = Path(__file__).parent.parent
    default_csv_file = script_dir / "output" / "fetch_notebooks_output.csv"
    default_bookmarks_dir = script_dir / "output" / "bookmarks"
    default_reviews_dir = script_dir / "output" / "reviews"
    default_output_dir = script_dir / "output" / "notes"
    
    # Get CSV file path
    csv_file = str(default_csv_file)
    if len(sys.argv) > 1:
        csv_file = sys.argv[1]
    
    if not os.path.exists(csv_file):
        print(f"Error: CSV file not found: {csv_file}")
        sys.exit(1)
    
    # Get directories
    bookmarks_dir = str(default_bookmarks_dir)
    if len(sys.argv) > 2:
        bookmarks_dir = sys.argv[2]
    
    reviews_dir = str(default_reviews_dir)
    if len(sys.argv) > 3:
        reviews_dir = sys.argv[3]
    
    output_dir = str(default_output_dir)
    if len(sys.argv) > 4:
        output_dir = sys.argv[4]
    
    # Read book IDs from CSV
    books = read_book_ids_from_csv(csv_file)
    
    if not books:
        print("No books found in CSV file.")
        sys.exit(1)
    
    print(f"\nStarting to merge notes for {len(books)} book(s)...\n")
    
    success_count = 0
    skipped_count = 0
    
    for i, book in enumerate(books, 1):
        book_id = book['bookId']
        book_title = book.get('title', f'Book_{book_id}')
        
        print(f"[{i}/{len(books)}] Processing: {book_title} (ID: {book_id})")
        
        # Read bookmarks and reviews
        bookmarks_file = os.path.join(bookmarks_dir, f"{book_id}.csv")
        reviews_file = os.path.join(reviews_dir, f"{book_id}.csv")
        
        bookmarks = read_bookmarks_csv(bookmarks_file)
        reviews = read_reviews_csv(reviews_file)
        
        if not bookmarks and not reviews:
            print(f"  No bookmarks or reviews found, skipping\n")
            skipped_count += 1
            continue
        
        print(f"  Found {len(bookmarks)} bookmark(s) and {len(reviews)} review(s)")
        
        # Merge notes
        merged_notes = merge_notes(bookmarks, reviews, book)
        
        if not merged_notes:
            print(f"  No notes after merging, skipping\n")
            skipped_count += 1
            continue
        
        # Skip if notes count is less than 30
        if len(merged_notes) < 30:
            print(f"  Only {len(merged_notes)} note(s), less than 30, skipping\n")
            skipped_count += 1
            continue
        
        # Save to CSV
        file_path = save_notes_to_csv(merged_notes, book_id, output_dir)
        print(f"  Saved {len(merged_notes)} note(s) to: {file_path}\n")
        success_count += 1
    
    # Print summary
    print("\n" + "="*60)
    print("Summary:")
    print(f"  Total books: {len(books)}")
    print(f"  Successfully merged: {success_count}")
    print(f"  Skipped: {skipped_count}")
    print(f"  Output directory: {output_dir}")
    print("="*60)


if __name__ == "__main__":
    main()

