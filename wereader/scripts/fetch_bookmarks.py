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
import argparse
from pathlib import Path
from typing import Optional, List, Dict, Any
import time
from datetime import datetime


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
            
            # Debug: Print response structure if no bookmarks found
            updated = data.get('updated', [])
            if not updated:
                print(f"  🔍 Debug: API Response structure:")
                print(f"     URL: {url}")
                print(f"     Status: {response.status_code}")
                print(f"     Response keys: {list(data.keys())[:20]}")
                if 'errcode' in data or 'errCode' in data:
                    err_code = data.get('errcode') or data.get('errCode')
                    err_msg = data.get('errMsg', '')
                    print(f"     Error code: {err_code}")
                    print(f"     Error message: {err_msg}")
                # Print first 500 chars of response for debugging
                response_str = str(data)[:500]
                print(f"     Response preview: {response_str}...")
            
            # Check for error codes (both errcode and errCode formats)
            err_code = data.get('errcode') or data.get('errCode')
            err_msg = data.get('errMsg', '')
            
            if err_code == -2012:
                print(f"  ❌ Error: Cookie expired (errCode -2012). Please refresh your cookie.")
                return None
            elif err_code == -2010:
                print(f"  ❌ Error: User not found (errCode -2010). Error message: {err_msg}")
                print(f"     This usually means the cookie is invalid or expired. Please refresh your cookie.")
                return None
            elif err_code and err_code != 0:
                print(f"  ⚠️  Warning: API returned error code {err_code}: {err_msg}")
                # Continue processing but log the error
            
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
    
    # Define columns: book metadata first, then bookmark fields, then timestamp columns
    columns = ['bookId', 'title', 'author', 'categories', 'bookmarkId', 'markText', 'chapterName', 'chapterUid', 'colorStyle', 'style', 'createTime', 'created_at', 'updated_at']
    
    # Get current timestamp
    current_time = datetime.now().isoformat()
    
    # Write CSV file
    with open(file_path, 'w', encoding='utf-8', newline='') as f:
        # Use QUOTE_MINIMAL to properly quote fields containing special characters or newlines
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction='ignore',
                                quoting=csv.QUOTE_MINIMAL)
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
                    # Replace newlines with spaces for better CSV readability
                    row[col] = str(value).replace('\n', ' ').replace('\r', ' ')
            # Add timestamp columns
            row['created_at'] = current_time
            row['updated_at'] = current_time
            writer.writerow(row)
    
    return str(file_path)


def main():
    """Main function"""
    # Default paths (parent directory, same level as scripts folder)
    script_dir = Path(__file__).parent.parent
    default_cookie_file = script_dir / "cookies.txt"
    default_csv_file = script_dir / "output" / "fetch_notebooks_output.csv"
    default_output_dir = script_dir / "output" / "bookmarks"
    
    parser = argparse.ArgumentParser(
        description='WeRead Bookmark Fetcher: 从 CSV 文件中读取书籍列表，获取每本书的书签并保存到单独的 CSV 文件',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
示例：
  python fetch_bookmarks.py --cookie cookies.txt
  python fetch_bookmarks.py --cookie cookies.txt --csv-file output/books.csv
  python fetch_bookmarks.py --cookie cookies.txt --book-id 3300064831
  
默认路径：
  Cookie 文件: {default_cookie_file}
  CSV 文件: {default_csv_file}
  输出目录: {default_output_dir}
        """
    )
    
    parser.add_argument('--cookie', '--cookie-file', dest='cookie', type=str, default=None,
                       help=f'Cookie 文件路径或 Cookie 字符串（可选，默认从 {default_cookie_file} 读取）')
    parser.add_argument('--csv-file', '--csv', dest='csv_file', type=str, default=str(default_csv_file),
                       help=f'包含书籍列表的 CSV 文件路径（默认: {default_csv_file}）')
    parser.add_argument('--output-dir', '--output', dest='output_dir', type=str, default=str(default_output_dir),
                       help=f'书签输出目录（默认: {default_output_dir}）')
    parser.add_argument('--book-id', '--id', dest='book_id', type=str, default=None,
                       help='书籍ID（可选，如果提供则只处理该书籍）')
    
    args = parser.parse_args()
    
    # Get cookie
    cookie = None
    
    if args.cookie:
        if os.path.exists(args.cookie) or args.cookie.endswith('.txt'):
            cookie = parse_netscape_cookie_file(args.cookie)
        else:
            cookie = args.cookie
    elif default_cookie_file.exists():
        cookie = parse_netscape_cookie_file(str(default_cookie_file))
    
    if not cookie:
        print("错误：未找到 Cookie")
        print(f"请使用 --cookie 参数指定 Cookie 文件或字符串，或将 Cookie 文件放在: {default_cookie_file}")
        sys.exit(1)
    
    # Get CSV file path
    csv_file = args.csv_file
    if not os.path.exists(csv_file):
        print(f"错误：CSV 文件不存在: {csv_file}")
        sys.exit(1)
    
    # Get output directory
    output_dir = args.output_dir
    
    # Initialize API client
    api = WeReadBookmarkAPI(cookie)
    
    filter_book_id = args.book_id
    
    # Read book IDs from CSV
    books = read_book_ids_from_csv(csv_file)
    
    if not books:
        print("No books found in CSV file.")
        sys.exit(1)
    
    # Filter by book ID if provided
    if filter_book_id:
        books = [book for book in books if book.get('bookId', '') == filter_book_id]
        if not books:
            print(f"No book found with ID: {filter_book_id}")
            sys.exit(1)
        print(f"Filtering to book ID: {filter_book_id}")
    
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
        err_msg = data.get('errMsg', '')
        
        if err_code == -2012:
            print(f"  ❌ Error: Cookie expired (errCode -2012). Please refresh your cookie.\n")
            error_count += 1
            # Stop processing if cookie is expired
            if i == 1:
                print("  Stopping: Cookie expired. Please update your cookie file and try again.")
                break
            continue
        elif err_code == -2010:
            print(f"  ❌ Error: User not found (errCode -2010). Error message: {err_msg}")
            print(f"     This usually means the cookie is invalid or expired. Please refresh your cookie.\n")
            error_count += 1
            # Stop processing if user not found
            if i == 1:
                print("  Stopping: User not found. Please update your cookie file and try again.")
                break
            continue
        elif err_code and err_code != 0:
            print(f"  ⚠️  Warning: API returned error code {err_code}: {err_msg}")
            # Continue processing but log the error
        
        # Extract bookmarks from response
        updated = data.get('updated', [])
        
        # Check for alternative data structures
        if not updated:
            # Try other possible fields
            if 'bookmarks' in data:
                updated = data.get('bookmarks', [])
                print(f"  🔍 Found 'bookmarks' field with {len(updated)} items")
            elif 'data' in data and isinstance(data.get('data'), list):
                updated = data.get('data', [])
                print(f"  🔍 Found 'data' field with {len(updated)} items")
        
        if not updated:
            print(f"  ⚠️  No bookmarks found in response")
            print(f"     This might indicate:")
            print(f"     1. The book has no bookmarks/highlights")
            print(f"     2. Cookie is invalid or expired (check error codes above)")
            print(f"     3. API response structure changed\n")
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

