#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WeRead Bookmark Fetcher
Fetches bookmarks (highlights) for each book from CSV file and saves to separate CSV files
"""

import requests
import json
import csv
import sys
import os
from pathlib import Path
from typing import Optional, List, Dict, Any
import time


class WeReadBookmarkAPI:
    """WeRead Bookmark API client"""
    
    BASE_URL = "https://weread.qq.com"
    
    def __init__(self, cookie: str):
        """
        Initialize API client with cookie
        
        Args:
            cookie: Cookie string from browser
        """
        self.cookie = cookie
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/73.0.3683.103 Safari/537.36',
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept': 'application/json, text/plain, */*',
            'Cookie': cookie
        })
    
    def get_bookmarks(self, book_id: str) -> Optional[dict]:
        """
        Fetch bookmarks (highlights) for a book
        
        Args:
            book_id: Book ID
        
        Returns:
            Response JSON data or None if error
        """
        url = f"{self.BASE_URL}/web/book/bookmarklist?bookId={book_id}"
        
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            # Check for error codes (both errcode and errCode formats)
            err_code = data.get('errcode') or data.get('errCode')
            if err_code == -2012:
                print(f"  Error: Cookie expired (errCode -2012). Please refresh your cookie.")
                return None
            
            return data
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                print(f"  Error: Unauthorized (401) for book {book_id}. Cookie may be invalid.")
            else:
                print(f"  HTTP Error for book {book_id}: {e}")
            return None
        except requests.exceptions.RequestException as e:
            print(f"  Request Error for book {book_id}: {e}")
            return None
        except json.JSONDecodeError as e:
            print(f"  JSON Decode Error for book {book_id}: {e}")
            return None


def parse_netscape_cookie_file(cookie_file: str) -> Optional[str]:
    """
    Parse Netscape format cookie file and extract cookies
    
    Args:
        cookie_file: Path to Netscape cookie file
    
    Returns:
        Cookie string in format "name=value; name=value" or None if error
    """
    cookie_file_path = Path(cookie_file)
    
    if not cookie_file_path.exists():
        print(f"Error: Cookie file not found: {cookie_file}")
        return None
    
    cookies = []
    
    try:
        with open(cookie_file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                
                # Skip empty lines and comments
                if not line or line.startswith('#'):
                    continue
                
                # Parse Netscape cookie format
                parts = line.split('\t')
                if len(parts) >= 7:
                    name = parts[5].strip()
                    value = parts[6].strip()
                    
                    if name and value:
                        cookies.append(f"{name}={value}")
        
        if not cookies:
            print("Error: No cookies found in file.")
            return None
        
        cookie_string = '; '.join(cookies)
        print(f"Successfully loaded {len(cookies)} cookie(s) from {cookie_file}")
        return cookie_string
        
    except Exception as e:
        print(f"Error reading cookie file: {e}")
        return None


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


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to remove invalid characters
    
    Args:
        filename: Original filename
    
    Returns:
        Sanitized filename
    """
    # Remove invalid characters for filename
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    
    # Limit length
    if len(filename) > 200:
        filename = filename[:200]
    
    return filename


def save_bookmarks_to_csv(bookmarks: List[Dict], book_id: str, book_metadata: Dict[str, str], output_dir: str) -> str:
    """
    Save bookmarks to CSV file
    
    Args:
        bookmarks: List of bookmark dictionaries
        book_id: Book ID for filename
        book_metadata: Dictionary with bookId, title, author, categories
        output_dir: Output directory
    
    Returns:
        Path to saved file
    """
    # Use bookId for filename
    filename = f"{book_id}.csv"
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    file_path = output_path / filename
    
    # Define columns: book metadata first, then bookmark fields
    columns = ['bookId', 'title', 'author', 'categories', 'bookmarkId', 'markText', 'chapterName', 'chapterUid', 'colorStyle', 'style', 'createTime']
    
    # Write CSV file
    with open(file_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction='ignore')
        writer.writeheader()
        
        for bookmark in bookmarks:
            row = {}
            # Add book metadata to each row
            row['bookId'] = book_metadata.get('bookId', '')
            row['title'] = book_metadata.get('title', '')
            row['author'] = book_metadata.get('author', '')
            row['categories'] = book_metadata.get('categories', '')
            # Add bookmark fields
            for col in ['bookmarkId', 'markText', 'chapterName', 'chapterUid', 'colorStyle', 'style', 'createTime']:
                value = bookmark.get(col, '')
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
    default_cookie_file = script_dir / "cookies.txt"
    default_csv_file = script_dir / "output" / "fetch_notebooks_output.csv"
    default_output_dir = script_dir / "output" / "bookmarks"
    
    # Get cookie
    cookie = None
    
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if os.path.exists(arg) or arg.endswith('.txt'):
            cookie = parse_netscape_cookie_file(arg)
        else:
            cookie = arg
    elif default_cookie_file.exists():
        cookie = parse_netscape_cookie_file(str(default_cookie_file))
    
    if not cookie:
        print("Error: Cookie not found. Please provide cookie file or string.")
        print(f"Usage: python fetch_bookmarks.py [cookie_file|cookie_string] [csv_file] [output_dir]")
        sys.exit(1)
    
    # Get CSV file path
    csv_file = default_csv_file
    if len(sys.argv) > 2:
        csv_file = sys.argv[2]
    
    if not os.path.exists(csv_file):
        print(f"Error: CSV file not found: {csv_file}")
        sys.exit(1)
    
    # Get output directory
    output_dir = str(default_output_dir)
    if len(sys.argv) > 3:
        output_dir = sys.argv[3]
    
    # Initialize API client
    api = WeReadBookmarkAPI(cookie)
    
    # Read book IDs from CSV
    books = read_book_ids_from_csv(csv_file)
    
    if not books:
        print("No books found in CSV file.")
        sys.exit(1)
    
    print(f"\nStarting to fetch bookmarks for {len(books)} book(s)...\n")
    
    success_count = 0
    error_count = 0
    no_bookmarks_count = 0
    
    for i, book in enumerate(books, 1):
        book_id = book['bookId']
        book_title = book.get('title', f'Book_{book_id}')
        
        print(f"[{i}/{len(books)}] Fetching bookmarks for: {book_title} (ID: {book_id})")
        
        # Fetch bookmarks
        data = api.get_bookmarks(book_id)
        
        if data is None:
            print(f"  Failed to fetch bookmarks\n")
            error_count += 1
            continue
        
        # Check for error codes in response
        err_code = data.get('errcode') or data.get('errCode')
        if err_code == -2012:
            print(f"  Error: Cookie expired (errCode -2012). Please refresh your cookie.\n")
            error_count += 1
            # Stop processing if cookie is expired
            if i == 1:
                print("  Stopping: Cookie expired. Please update your cookie file and try again.")
                break
            continue
        
        # Extract bookmarks from response
        updated = data.get('updated', [])
        
        if not updated:
            print(f"  No bookmarks found\n")
            no_bookmarks_count += 1
            continue
        
        # Sort by chapterUid (ascending), then by createTime (ascending) if chapterUid is the same
        updated.sort(key=lambda x: (x.get('chapterUid', 0), x.get('createTime', 0)))
        
        # Save to CSV with book metadata
        file_path = save_bookmarks_to_csv(updated, book_id, book, output_dir)
        print(f"  Saved {len(updated)} bookmark(s) to: {file_path}\n")
        success_count += 1
        
        # Add a small delay to avoid rate limiting
        time.sleep(0.5)
    
    # Print summary
    print("\n" + "="*60)
    print("Summary:")
    print(f"  Total books: {len(books)}")
    print(f"  Successfully fetched: {success_count}")
    print(f"  No bookmarks: {no_bookmarks_count}")
    print(f"  Errors: {error_count}")
    print(f"  Output directory: {output_dir}")
    print("="*60)


if __name__ == "__main__":
    main()

