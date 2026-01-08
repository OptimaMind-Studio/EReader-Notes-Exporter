#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM 功能主脚本
依次调用概念提取、大纲生成和学习指南生成功能
"""

import sys
import os
import subprocess
import argparse
from pathlib import Path


def run_script(script_path: Path, args: list) -> bool:
    """
    运行指定的 Python 脚本
    
    Args:
        script_path: 脚本路径
        args: 命令行参数列表
    
    Returns:
        如果成功返回 True，否则返回 False
    """
    try:
        # 构建完整的命令
        cmd = [sys.executable, str(script_path)] + args
        print(f"\n{'='*60}")
        print(f"运行: {' '.join(cmd)}")
        print(f"{'='*60}\n")
        
        # 运行脚本
        result = subprocess.run(cmd, check=False)
        
        if result.returncode == 0:
            print(f"\n✓ {script_path.name} 执行成功")
            return True
        else:
            print(f"\n✗ {script_path.name} 执行失败 (退出码: {result.returncode})")
            return False
    
    except Exception as e:
        print(f"\n✗ 运行 {script_path.name} 时出错: {e}")
        return False


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='LLM 功能主脚本：依次执行概念提取、大纲生成和学习指南生成',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  # 使用 bookID
  python llm/llm.py --book-id 3300089819
  
  # 使用书名
  python llm/llm.py --title "极简央行课"
  
  # 指定章节（仅用于学习指南生成）
  python llm/llm.py --book-id 3300089819 --chapter "第一章"
  
  # 跳过某些步骤
  python llm/llm.py --book-id 3300089819 --skip-concepts
  python llm/llm.py --book-id 3300089819 --skip-outline
  python llm/llm.py --book-id 3300089819 --skip-guidebook
        """
    )
    
    # 书名和 bookID 二选一
    book_group = parser.add_mutually_exclusive_group(required=True)
    book_group.add_argument('--title', '--book-title', dest='book_title', type=str,
                           help='书籍名称')
    book_group.add_argument('--book-id', '--id', dest='book_id', type=str,
                           help='书籍ID')
    
    # 章节名（可选，仅用于学习指南生成）
    parser.add_argument('--chapter', '--chapter-name', dest='chapter_name', type=str, default=None,
                       help='章节名称（可选，仅用于学习指南生成，如果不提供则处理整本书）')
    
    # 跳过某些步骤
    parser.add_argument('--skip-concepts', dest='skip_concepts', action='store_true',
                       help='跳过概念提取步骤')
    parser.add_argument('--skip-outline', dest='skip_outline', action='store_true',
                       help='跳过大纲生成步骤')
    parser.add_argument('--skip-guidebook', dest='skip_guidebook', action='store_true',
                       help='跳过学习指南生成步骤')
    
    # API key（可选）
    parser.add_argument('--api-key', type=str,
                       help='Gemini API 密钥（可选，优先从环境变量 GEMINI_API_KEY 或 GOOGLE_API_KEY 读取）')
    
    # 学习指南的并发度
    parser.add_argument('--concurrency', '--parallel', dest='concurrency', type=int, default=10,
                       help='学习指南生成的并行度（默认: 10）')
    
    # 大纲生成的角色
    parser.add_argument('--role', type=str, default='学习者',
                       help='大纲生成的角色（默认: 学习者）')
    
    args = parser.parse_args()
    
    # 获取脚本所在目录
    script_dir = Path(__file__).parent
    scripts_dir = script_dir / "scripts"
    
    # 检查脚本目录是否存在
    if not scripts_dir.exists():
        print(f"❌ 错误：脚本目录不存在: {scripts_dir}")
        sys.exit(1)
    
    # 构建基础参数（book-id 或 title）
    base_args = []
    if args.book_id:
        base_args.extend(['--book-id', args.book_id])
    elif args.book_title:
        base_args.extend(['--title', args.book_title])
    
    # 添加 API key（如果提供）
    if args.api_key:
        base_args.extend(['--api-key', args.api_key])
    
    # 记录执行结果
    results = {}
    
    # 1. 概念提取
    if not args.skip_concepts:
        extract_concepts_script = scripts_dir / "extract_concepts.py"
        if extract_concepts_script.exists():
            concepts_args = base_args.copy()
            success = run_script(extract_concepts_script, concepts_args)
            results['concepts'] = success
        else:
            print(f"⚠️  警告：脚本不存在: {extract_concepts_script}")
            results['concepts'] = False
    else:
        print("\n跳过概念提取步骤")
        results['concepts'] = None
    
    # 2. 大纲生成
    if not args.skip_outline:
        generate_outline_script = scripts_dir / "generate_outline.py"
        if generate_outline_script.exists():
            outline_args = base_args.copy()
            outline_args.extend(['--role', args.role])
            success = run_script(generate_outline_script, outline_args)
            results['outline'] = success
        else:
            print(f"⚠️  警告：脚本不存在: {generate_outline_script}")
            results['outline'] = False
    else:
        print("\n跳过大纲生成步骤")
        results['outline'] = None
    
    # 3. 学习指南生成
    if not args.skip_guidebook:
        generate_guidebook_script = scripts_dir / "generate_guidebook.py"
        if generate_guidebook_script.exists():
            guidebook_args = base_args.copy()
            if args.chapter_name:
                guidebook_args.extend(['--chapter', args.chapter_name])
            guidebook_args.extend(['--concurrency', str(args.concurrency)])
            success = run_script(generate_guidebook_script, guidebook_args)
            results['guidebook'] = success
        else:
            print(f"⚠️  警告：脚本不存在: {generate_guidebook_script}")
            results['guidebook'] = False
    else:
        print("\n跳过学习指南生成步骤")
        results['guidebook'] = None
    
    # 打印总结
    print(f"\n{'='*60}")
    print("执行总结")
    print(f"{'='*60}")
    
    for step, result in results.items():
        if result is None:
            status = "跳过"
        elif result:
            status = "✓ 成功"
        else:
            status = "✗ 失败"
        
        step_name = {
            'concepts': '概念提取',
            'outline': '大纲生成',
            'guidebook': '学习指南生成'
        }.get(step, step)
        
        print(f"  {step_name}: {status}")
    
    # 如果有失败的步骤，返回非零退出码
    if any(r is False for r in results.values()):
        sys.exit(1)
    else:
        print(f"\n✓ 所有步骤执行完成")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n错误：{e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

