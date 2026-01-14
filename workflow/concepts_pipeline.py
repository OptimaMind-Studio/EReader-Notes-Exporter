#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Concepts 自动化流程脚本
# 执行：fetch (wereader/fetch.py 完整流程) -> extract concepts
#
# 用法：
#   python concepts_pipeline.py                    # 处理所有书籍
#   python concepts_pipeline.py --book-id 3300089819
#   python concepts_pipeline.py --book-name "极简央行课"
#

import sys
import subprocess
import argparse
import csv
from pathlib import Path
from typing import Optional, List


class Colors:
    """终端颜色"""
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'  # No Color


def print_info(msg: str):
    """打印信息"""
    print(f"{Colors.BLUE}[INFO]{Colors.NC} {msg}")


def print_success(msg: str):
    """打印成功消息"""
    print(f"{Colors.GREEN}[SUCCESS]{Colors.NC} {msg}")


def print_warning(msg: str):
    """打印警告消息"""
    print(f"{Colors.YELLOW}[WARNING]{Colors.NC} {msg}")


def print_error(msg: str):
    """打印错误消息"""
    print(f"{Colors.RED}[ERROR]{Colors.NC} {msg}")


def print_step(msg: str):
    """打印步骤标题"""
    print("")
    print("=" * 60)
    print(msg)
    print("=" * 60)


class ConceptsPipeline:
    """Concepts 自动化流程"""
    
    def __init__(self):
        """初始化路径"""
        self.script_dir = Path(__file__).parent
        self.project_root = self.script_dir.parent
        
        # 默认路径
        self.wereader_dir = self.project_root / "wereader"
        self.concepts_script = self.project_root / "llm" / "scripts" / "extract_concepts.py"
        self.fetch_script = self.project_root / "wereader" / "fetch.py"
        self.cookie_file = self.wereader_dir / "cookies.txt"
        self.books_csv = self.wereader_dir / "output" / "fetch_notebooks_output.csv"
    
    def check_prerequisites(self):
        """检查必要的文件是否存在"""
        if not self.cookie_file.exists():
            print_error(f"Cookie 文件不存在: {self.cookie_file}")
            sys.exit(1)
        
        if not self.fetch_script.exists():
            print_error(f"Fetch 脚本不存在: {self.fetch_script}")
            sys.exit(1)
        
        if not self.concepts_script.exists():
            print_error(f"Concepts 提取脚本不存在: {self.concepts_script}")
            sys.exit(1)
    
    def get_all_book_ids(self) -> List[str]:
        """获取所有书籍ID列表"""
        if not self.books_csv.exists():
            print_warning("书籍列表文件不存在，将先执行 fetch 步骤")
            return []
        
        book_ids = []
        try:
            with open(self.books_csv, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    book_id = row.get('bookId', '').strip()
                    if book_id:
                        book_ids.append(book_id)
        except Exception as e:
            print_error(f"读取书籍列表失败: {e}")
            return []
        
        return book_ids
    
    def run_fetch(self, book_id: Optional[str] = None) -> bool:
        """
        执行 fetch 步骤
        调用 wereader/fetch.py，执行完整流程：
        1. Fetch books list
        2. Fetch bookmarks
        3. Fetch reviews
        4. Merge notes
        """
        print_step("步骤 1: Fetch 数据（包含 fetch books, bookmarks, reviews 和 merge notes）")
        
        args = [sys.executable, str(self.fetch_script)]
        if book_id:
            args.extend(['--book-id', book_id])
            print_info(f"处理书籍 ID: {book_id}")
        else:
            print_info("处理所有书籍")
        
        try:
            result = subprocess.run(
                args,
                cwd=str(self.project_root),
                check=False
            )
            if result.returncode == 0:
                print_success("Fetch 完成")
                return True
            else:
                print_error("Fetch 失败")
                return False
        except Exception as e:
            print_error(f"Fetch 执行出错: {e}")
            return False
    
    def run_extract_concepts(self, book_id: Optional[str] = None, book_name: Optional[str] = None) -> bool:
        """执行 extract concepts 步骤"""
        print_step("步骤 2: 提取概念")
        
        args = [sys.executable, str(self.concepts_script)]
        if book_id:
            args.extend(['--book-id', book_id])
            print_info(f"处理书籍 ID: {book_id}")
        elif book_name:
            args.extend(['--title', book_name])
            print_info(f"处理书籍名称: {book_name}")
        else:
            print_info("处理所有书籍")
        
        try:
            result = subprocess.run(
                args,
                cwd=str(self.project_root),
                check=False
            )
            if result.returncode == 0:
                print_success("概念提取完成")
                return True
            else:
                print_error("概念提取失败")
                return False
        except Exception as e:
            print_error(f"概念提取执行出错: {e}")
            return False
    
    def process_single_book(self, book_id: Optional[str] = None, book_name: Optional[str] = None) -> bool:
        """处理单本书"""
        book_label = book_id or book_name or "所有书籍"
        print_info(f"开始处理书籍: {book_label}")
        
        # Step 1: Fetch
        if not self.run_fetch(book_id):
            print_error("Fetch 步骤失败，停止流程")
            return False
        
        # Step 2: Extract Concepts
        if not self.run_extract_concepts(book_id, book_name):
            print_error("概念提取失败，停止流程")
            return False
        
        print_success(f"书籍处理完成: {book_label}")
        return True
    
    def process_all_books(self):
        """处理所有书籍"""
        print_info("未指定书籍，将处理所有书籍")
        
        # Step 1: 先执行一次 fetch（所有书籍）
        # 如果书籍列表文件不存在，才执行 fetch
        if not self.books_csv.exists():
            print_info("书籍列表文件不存在，先执行 fetch...")
            if not self.run_fetch():
                print_error("无法获取书籍数据")
                sys.exit(1)
        else:
            print_info("书籍列表文件已存在，跳过 fetch 步骤")
            print_info("如需更新数据，请先手动运行 fetch 脚本")
        
        # 获取所有书籍ID
        print_info("获取所有书籍ID...")
        book_ids = self.get_all_book_ids()
        
        if not book_ids:
            print_error("未找到任何书籍")
            print_info("请先运行 fetch 步骤获取书籍列表")
            sys.exit(1)
        
        print_info(f"找到 {len(book_ids)} 本书籍")
        
        # Step 2: 逐本提取概念
        success_count = 0
        fail_count = 0
        
        for bid in book_ids:
            print("")
            print_info("=" * 42)
            print_info(f"处理书籍 ID: {bid}")
            print_info("=" * 42)
            
            # Step 2: Extract Concepts
            if not self.run_extract_concepts(bid, None):
                print_warning(f"书籍 {bid} 的概念提取失败")
                fail_count += 1
            else:
                success_count += 1
        
        # 总结
        print("")
        print_step("处理完成")
        print_info(f"成功: {success_count} 本")
        print_info(f"失败: {fail_count} 本")
        print_info(f"总计: {len(book_ids)} 本")
    
    def run(self, book_id: Optional[str] = None, book_name: Optional[str] = None):
        """运行主流程"""
        print_info("Concepts 自动化流程")
        print_info(f"项目根目录: {self.project_root}")
        
        # 检查前置条件
        self.check_prerequisites()
        
        # 如果指定了 book-id 或 book-name，只处理单本书
        if book_id or book_name:
            self.process_single_book(book_id, book_name)
        else:
            # 处理所有书籍
            self.process_all_books()
        
        print_success("所有流程执行完成！")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='Concepts 自动化流程：fetch -> extract concepts',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python concepts_pipeline.py                    # 处理所有书籍
  python concepts_pipeline.py --book-id 3300089819
  python concepts_pipeline.py --book-name "极简央行课"
        """
    )
    
    book_group = parser.add_mutually_exclusive_group()
    book_group.add_argument('--book-id', '--id', dest='book_id', type=str, default=None,
                          help='书籍ID（与 --book-name 二选一）')
    book_group.add_argument('--book-name', '--title', dest='book_name', type=str, default=None,
                           help='书籍名称（与 --book-id 二选一）')
    
    args = parser.parse_args()
    
    # 创建 pipeline 实例并运行
    pipeline = ConceptsPipeline()
    pipeline.run(book_id=args.book_id, book_name=args.book_name)


if __name__ == "__main__":
    main()

