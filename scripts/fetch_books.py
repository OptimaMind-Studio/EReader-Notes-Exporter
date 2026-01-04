#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WeRead Notebook Fetcher
Fetches user notebooks from WeRead API and saves to local file
"""

import requests
import json
import sys
import os
import csv
from typing import Optional, Dict, Any, List
from pathlib import Path


class WeReadAPI:
    """WeRead API client"""
    
    BASE_URL = "https://weread.qq.com"
    
    def __init__(self, cookie: str):
        """
        Initialize API client with cookie
        
        Args:
            cookie: Cookie string from browser (e.g., "wr_name=xxx; wr_skey=xxx; ...")
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
    
    def get_notebooks(self) -> Optional[dict]:
        """
        Fetch user notebooks from WeRead API
        
        Returns:
            Response JSON data or None if error
        """
        url = f"{self.BASE_URL}/api/user/notebook"
        
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            # Check for error codes (both errcode and errCode formats)
            err_code = data.get('errcode') or data.get('errCode')
            if err_code == -2012:
                print("Error: Cookie expired (errCode -2012). Please refresh your cookie.")
                return None
            
            return data
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                print("Error: Unauthorized (401). Cookie may be invalid or expired.")
            else:
                print(f"HTTP Error: {e}")
            return None
        except requests.exceptions.RequestException as e:
            print(f"Request Error: {e}")
            return None
        except json.JSONDecodeError as e:
            print(f"JSON Decode Error: {e}")
            print(f"Response text: {response.text[:500]}")
            return None
    
    def get_progress(self, book_id: str) -> Optional[dict]:
        """
        Fetch reading progress for a book
        
        Args:
            book_id: Book ID
        
        Returns:
            Response JSON data or None if error
        """
        url = f"{self.BASE_URL}/web/book/getProgress?bookId={book_id}"
        
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            # Check for error codes (both errcode and errCode formats)
            err_code = data.get('errcode') or data.get('errCode')
            if err_code == -2012:
                print(f"  Error: Cookie expired (errCode -2012) for book {book_id}")
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
    
    def save_to_file(self, data: dict, filename: Optional[str] = None, output_dir: Optional[str] = None) -> str:
        """
        Save notebook data to JSON file
        
        Args:
            data: Notebook data dictionary
            filename: Output filename (optional, defaults to "fetch notebooks output.json")
            output_dir: Output directory (optional, defaults to 'output' folder)
        
        Returns:
            Path to saved file
        """
        if filename is None:
            filename = "fetch_notebooks_output.json"
        
        # Ensure filename ends with .json
        if not filename.endswith('.json'):
            filename += '.json'
        
        # Determine output directory - use output folder in wereader directory
        if output_dir is None:
            script_dir = Path(__file__).parent.parent
            output_dir = str(script_dir / "output")
        
        # Create output directory if it doesn't exist
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Full file path
        file_path = output_path / filename
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        return str(file_path)
    
    def save_to_csv(self, data: dict, filename: Optional[str] = None, output_dir: Optional[str] = None) -> str:
        """
        Save notebook data to CSV file
        
        Args:
            data: Notebook data dictionary
            filename: Output filename (optional, defaults to "fetch_notebooks_output.csv")
            output_dir: Output directory (optional, defaults to 'output' folder)
        
        Returns:
            Path to saved file
        """
        if filename is None:
            filename = "fetch_notebooks_output.csv"
        
        # Ensure filename ends with .csv
        if not filename.endswith('.csv'):
            filename += '.csv'
        
        # Determine output directory - use output folder in wereader directory
        if output_dir is None:
            script_dir = Path(__file__).parent.parent
            output_dir = str(script_dir / "output")
        
        # Create output directory if it doesn't exist
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Full file path
        file_path = output_path / filename
        
        books = data.get('books', [])
        if not books:
            print("Warning: No books to export to CSV.")
            return str(file_path)
        
        # Define important fields only (excluding price, status, rating, and other fields)
        important_fields = [
            # Basic info
            'bookId', 'title', 'author', 'translator',
            # Publication info
            'publishTime',
            # Category info
            'categories',
            # Reading info
            'lastChapterIdx',
            # User stats (from book_item)
            'noteCount', 'reviewCount', 'bookmarkCount',
            # Progress info (from getProgress API)
            'readingTime', 'finishTime'
        ]
        
        # Process books and extract only important fields
        processed_books = []
        
        for book_item in books:
            book_data = book_item.get('book', {})
            if not book_data:
                continue
            
            # Create a new dict with only important fields
            important_book = {}
            
            # Extract important fields from book_data
            for field in important_fields:
                if field in book_data:
                    value = book_data[field]
                    # Handle categories array - convert to readable string
                    if field == 'categories' and isinstance(value, list):
                        category_titles = [cat.get('title', '') for cat in value if isinstance(cat, dict)]
                        important_book[field] = '; '.join(category_titles) if category_titles else ''
                    elif isinstance(value, (dict, list)):
                        important_book[field] = json.dumps(value, ensure_ascii=False)
                    else:
                        important_book[field] = value
            
            # Add top-level fields from book_item (noteCount, reviewCount, bookmarkCount, progress fields)
            for field in ['noteCount', 'reviewCount', 'bookmarkCount', 'readingTime', 'finishTime']:
                if field in book_item:
                    important_book[field] = book_item[field]
            
            processed_books.append(important_book)
        
        # Use important_fields as column order
        columns = important_fields
        
        # Write CSV file
        with open(file_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=columns, extrasaction='ignore')
            writer.writeheader()
            for book in processed_books:
                # Convert all values to strings, handle None
                row = {}
                for key in columns:
                    value = book.get(key, '')
                    if value is None:
                        row[key] = ''
                    else:
                        row[key] = str(value)
                writer.writerow(row)
        
        return str(file_path)
    
    def _flatten_dict(self, d: Dict[str, Any], parent_key: str = '', sep: str = '_') -> Dict[str, Any]:
        """
        Flatten a nested dictionary
        
        Args:
            d: Dictionary to flatten
            parent_key: Parent key prefix
            sep: Separator for nested keys
        
        Returns:
            Flattened dictionary
        """
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(self._flatten_dict(v, new_key, sep=sep).items())
            elif isinstance(v, list):
                # For lists, convert to JSON string or join if simple values
                if v and isinstance(v[0], dict):
                    items.append((new_key, json.dumps(v, ensure_ascii=False)))
                else:
                    items.append((new_key, ', '.join(str(item) for item in v)))
            else:
                items.append((new_key, v))
        return dict(items)


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
                
                # Parse Netscape cookie format: domain\tflag\tpath\tsecure\texpiration\tname\tvalue
                parts = line.split('\t')
                if len(parts) >= 7:
                    # Extract name (6th column, index 5) and value (7th column, index 6)
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


def main():
    """Main function"""
    # Default cookie file path (parent directory, same level as scripts folder)
    script_dir = Path(__file__).parent.parent
    default_cookie_file = script_dir / "cookies.txt"
    
    cookie = None
    
    # Priority: 1. Command line argument (cookie file path or cookie string)
    #           2. Environment variable
    #           3. Default cookie file
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        # Check if argument is a file path
        if os.path.exists(arg) or arg.endswith('.txt'):
            cookie = parse_netscape_cookie_file(arg)
        else:
            # Treat as cookie string
            cookie = arg
    elif 'WEREAD_COOKIE' in os.environ:
        cookie = os.environ['WEREAD_COOKIE']
    elif default_cookie_file.exists():
        # Try to read from default cookie file
        cookie = parse_netscape_cookie_file(str(default_cookie_file))
    
    if not cookie:
        print("Usage:")
        print("  python fetch_notebooks.py [cookie_file_path|cookie_string]")
        print("  or")
        print("  export WEREAD_COOKIE='your_cookie_string'")
        print("  python fetch_notebooks.py")
        print("\nIf no arguments provided, will try to read from:")
        print(f"  {default_cookie_file}")
        print("\nExample:")
        print('  python fetch_notebooks.py "wr_name=xxx; wr_skey=yyy; ..."')
        print(f'  python fetch_notebooks.py "{default_cookie_file}"')
        sys.exit(1)
    
    # Initialize API client
    api = WeReadAPI(cookie)
    
    print("Fetching notebooks from WeRead API...")
    data = api.get_notebooks()
    
    if data is None:
        print("Failed to fetch notebooks.")
        sys.exit(1)
    
    # Check if we got books
    books = data.get('books', [])
    if not books:
        print("Warning: No books found in response.")
        print("Response data:", json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(f"Successfully fetched {len(books)} notebook(s).")
    
    # Fetch progress for each book
    print("\nFetching reading progress for each book...")
    import time
    for i, book_item in enumerate(books, 1):
        book_id = book_item.get('bookId', '')
        if not book_id:
            continue
        
        book_title = book_item.get('book', {}).get('title', f'Book_{book_id}')
        print(f"  [{i}/{len(books)}] Fetching progress for: {book_title} (ID: {book_id})")
        
        progress_data = api.get_progress(book_id)
        
        if progress_data and 'book' in progress_data:
            book_progress = progress_data['book']
            # Convert readingTime from seconds to hours
            reading_time_seconds = book_progress.get('readingTime', 0)
            if reading_time_seconds and reading_time_seconds > 0:
                book_item['readingTime'] = reading_time_seconds / 60 / 60  # Convert to hours
            else:
                book_item['readingTime'] = ''
            book_item['finishTime'] = book_progress.get('finishTime', '')
        else:
            # Set empty values if progress not available
            book_item['readingTime'] = ''
            book_item['finishTime'] = ''
        
        # Add a small delay to avoid rate limiting
        time.sleep(0.3)
    
    print("Progress fetching completed.\n")
    
    # Save to CSV file
    csv_filename = api.save_to_csv(data)
    print(f"CSV data saved to: {csv_filename}")
    
    # Print summary
    if books:
        print("\nNotebooks summary:")
        for i, book_item in enumerate(books[:10], 1):  # Show first 10
            book_id = book_item.get('bookId', 'N/A')
            # Get title and author from nested book object
            book_data = book_item.get('book', {})
            if not book_data:
                # Fallback: try direct access
                title = book_item.get('title', 'N/A')
                author = book_item.get('author', 'N/A')
            else:
                title = book_data.get('title', 'N/A')
                author = book_data.get('author', 'N/A')
            print(f"  {i}. {title} - {author} (ID: {book_id})")
        
        if len(books) > 10:
            print(f"  ... and {len(books) - 10} more")


if __name__ == "__main__":
    main()

