#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
学习大纲生成工具
从笔记 CSV 文件中按章节分组，使用 Gemini API 生成学习大纲
"""

import sys
import os
import csv
import json
import time
import re
import html
from pathlib import Path
from typing import Optional, List, Dict, Tuple
from collections import defaultdict
from google import genai

# 导入 prompt 模板
try:
    # 从项目根目录运行时
    from llm.prompts import OUTLINE_PROMPT_TEMPLATE
except ImportError:
    # 从 llm 目录运行时
    from prompts import OUTLINE_PROMPT_TEMPLATE


class OutlineGenerator:
    """使用 Gemini API 生成学习大纲"""
    
    PROMPT_TEMPLATE = OUTLINE_PROMPT_TEMPLATE
    
    def __init__(self, api_key: Optional[str] = None, role: str = "学习者"):
        """
        初始化 Gemini API 客户端
        
        Args:
            api_key: Gemini API 密钥，如果为 None 则从环境变量读取
            role: 角色（默认为"学习者"）
        """
        if api_key is None:
            api_key = os.environ.get('GOOGLE_API_KEY') or os.environ.get('GEMINI_API_KEY')
        
        if not api_key:
            raise ValueError(
                "请提供 Gemini API 密钥。可以通过以下方式：\n"
                "1. 作为参数传入：OutlineGenerator(api_key='your_key')\n"
                "2. 设置环境变量：export GEMINI_API_KEY='your_api_key' 或 export GOOGLE_API_KEY='your_api_key'"
            )
        
        self.client = genai.Client(api_key=api_key)
        self.role = role
    
    def _clean_json_string(self, json_str: str) -> str:
        """
        清理 JSON 字符串中的控制字符
        
        Args:
            json_str: 原始 JSON 字符串
        
        Returns:
            清理后的 JSON 字符串
        """
        # 移除字符串值外的控制字符（\x00-\x1F，除了 \n, \r, \t）
        # 这是一个复杂的问题，因为我们需要区分字符串值内外的控制字符
        
        # 简单方法：尝试修复常见的控制字符问题
        # 移除字符串值外的控制字符
        lines = json_str.split('\n')
        cleaned_lines = []
        in_string = False
        escape_next = False
        
        for line in lines:
            cleaned_line = []
            for char in line:
                if escape_next:
                    cleaned_line.append(char)
                    escape_next = False
                    continue
                
                if char == '\\':
                    escape_next = True
                    cleaned_line.append(char)
                    continue
                
                if char == '"' and not escape_next:
                    in_string = not in_string
                    cleaned_line.append(char)
                    continue
                
                # 如果是控制字符且不在字符串值中，跳过
                if not in_string and ord(char) < 32 and char not in ['\n', '\r', '\t']:
                    continue
                
                cleaned_line.append(char)
            
            cleaned_lines.append(''.join(cleaned_line))
        
        return '\n'.join(cleaned_lines)
    
    def generate_outline(self, mark_notes: str, review_notes: str, max_retries: int = 3) -> Dict[str, str]:
        """
        生成学习大纲
        
        Args:
            mark_notes: 划线笔记（包含章节标题和划线文本）
            review_notes: 点评笔记
            max_retries: 最大重试次数（当 HTML 解析失败时）
        
        Returns:
            包含 'markdown' 和 'html' 的字典
        """
        # 替换 prompt 模板中的占位符
        prompt = self.PROMPT_TEMPLATE.replace("{{划线笔记}}", mark_notes)
        prompt = prompt.replace("{{点评笔记}}", review_notes)
        
        last_error = None
        last_response_text = None
        
        for attempt in range(max_retries):
            try:
                # 如果不是第一次尝试，打印重试信息
                if attempt > 0:
                    print(f"  🔄 重试第 {attempt} 次...")
                
                response = self.client.models.generate_content(
                    model='gemini-2.0-flash-001',
                    contents=prompt,
                )
                
                # 获取响应文本
                if hasattr(response, 'text'):
                    response_text = response.text
                elif hasattr(response, 'candidates') and len(response.candidates) > 0:
                    response_text = response.candidates[0].content.parts[0].text
                else:
                    response_text = str(response)
                
                response_text = response_text.strip()
                last_response_text = response_text
                
                # 清理响应文本，提取 HTML 部分
                # 移除可能的 markdown 代码块标记（包括 ```html, ```, 等）
                if response_text.startswith('```'):
                    lines = response_text.split('\n')
                    start_idx = 1
                    end_idx = len(lines)
                    for i, line in enumerate(lines):
                        if line.strip().startswith('```') and i > 0:
                            end_idx = i
                            break
                    response_text = '\n'.join(lines[start_idx:end_idx])
                
                # 移除所有剩余的 markdown 代码块标记
                response_text = re.sub(r'^```[a-z]*\n?', '', response_text, flags=re.MULTILINE)
                response_text = re.sub(r'\n?```$', '', response_text, flags=re.MULTILINE)
                response_text = response_text.strip()
                
                # 验证和清理 HTML
                html_content = self._validate_and_clean_html(response_text)
                
                if html_content:
                    # 从 HTML 生成 markdown（简化版本）
                    markdown_content = self._html_to_markdown(html_content)
                    
                    return {
                        'markdown': markdown_content,
                        'html': html_content
                    }
                else:
                    # HTML 验证失败，重试
                    if attempt < max_retries - 1:
                        last_error = "HTML 格式验证失败"
                        print(f"  ⚠️  HTML 格式验证失败，重试...")
                        time.sleep(1)
                        continue
                    else:
                        # 如果重试次数用完，返回错误信息
                        error_text = response_text[:1000]
                        error_text = html.escape(error_text)
                        error_text = re.sub(r'```[a-z]*\n?', '', error_text)
                        error_text = re.sub(r'\n?```', '', error_text)
                        
                        return {
                            'markdown': f"HTML 格式验证失败\n\n原始响应：\n{response_text[:1000]}",
                            'html': f"<html><body><p>HTML 格式验证失败</p><pre>{error_text}</pre></body></html>"
                        }
            
            except Exception as e:
                last_error = str(e)
                error_msg = f"生成大纲时出错：{str(e)}"
                print(f"  ⚠️  {error_msg}")
                
                # 如果是网络错误或其他可重试的错误，且还有重试机会，继续重试
                if attempt < max_retries - 1:
                    time.sleep(1)  # 等待 1 秒后重试
                    continue
                
                # 如果重试次数用完，返回错误信息
                error_text = last_response_text[:1000] if last_response_text else '无响应'
                error_text = html.escape(error_text)
                error_text = re.sub(r'```[a-z]*\n?', '', error_text)
                error_text = re.sub(r'\n?```', '', error_text)
                
                return {
                    'markdown': error_msg,
                    'html': f"<html><body><p>{error_msg}</p><pre>{error_text}</pre></body></html>"
                }
        
        # 如果所有重试都失败，返回最后的错误信息
        error_text = last_response_text[:1000] if last_response_text else '无响应'
        error_text = html.escape(error_text)
        error_text = re.sub(r'```[a-z]*\n?', '', error_text)
        error_text = re.sub(r'\n?```', '', error_text)
        
        return {
            'markdown': f"生成大纲失败（已重试 {max_retries} 次）：{last_error}\n\n原始响应：\n{last_response_text[:1000] if last_response_text else '无响应'}",
            'html': f"<html><body><p>生成大纲失败（已重试 {max_retries} 次）：{last_error}</p><pre>{error_text}</pre></body></html>"
        }
    
    def _validate_and_clean_html(self, html_text: str) -> Optional[str]:
        """
        验证和清理 HTML 文本
        
        Args:
            html_text: 原始 HTML 文本
        
        Returns:
            清理后的 HTML 文本，如果无效则返回 None
        """
        if not html_text or not html_text.strip():
            return None
        
        # 检查是否包含基本的 HTML 标签
        if not re.search(r'<[hH][1-6]', html_text) and not re.search(r'<[pP]', html_text):
            # 如果没有 HTML 标签，可能不是 HTML 格式
            print(f"  ⚠️  响应中未找到 HTML 标签")
            return None
        
        # 清理控制字符（但保留字符串值中的合法转义字符）
        # 移除字符串值外的控制字符
        cleaned_html = self._clean_html_string(html_text)
        
        # 确保 HTML 是完整的（如果没有 html/body 标签，添加它们）
        if not re.search(r'<html', cleaned_html, re.IGNORECASE):
            # 如果没有完整的 HTML 结构，只返回内容部分
            # 调用者会负责包装
            return cleaned_html
        
        return cleaned_html
    
    def _clean_html_string(self, html_str: str) -> str:
        """
        清理 HTML 字符串中的控制字符
        
        Args:
            html_str: 原始 HTML 字符串
        
        Returns:
            清理后的 HTML 字符串
        """
        # 移除控制字符（除了 \n, \r, \t）
        result = []
        for char in html_str:
            if ord(char) < 32 and char not in ['\n', '\r', '\t']:
                continue
            result.append(char)
        
        return ''.join(result)
    
    def _html_to_markdown(self, html_content: str) -> str:
        """
        从 HTML 生成简化的 Markdown（用于兼容性）
        
        Args:
            html_content: HTML 内容
        
        Returns:
            Markdown 格式的文本
        """
        # 简单的 HTML 到 Markdown 转换
        # 移除 HTML 标签，保留文本内容
        markdown = html_content
        
        # 替换标题标签 - 使用 lambda 函数来处理反向引用
        def replace_header(match):
            level = int(match.group(1))
            text = match.group(2)
            return f'\n{"#" * level} {text}\n'
        
        markdown = re.sub(r'<h([1-6])>(.*?)</h\1>', replace_header, markdown, flags=re.IGNORECASE | re.DOTALL)
        
        # 替换段落标签
        markdown = re.sub(r'<p>(.*?)</p>', r'\1\n\n', markdown, flags=re.IGNORECASE | re.DOTALL)
        
        # 替换加粗标签
        markdown = re.sub(r'<strong>(.*?)</strong>', r'**\1**', markdown, flags=re.IGNORECASE | re.DOTALL)
        markdown = re.sub(r'<b>(.*?)</b>', r'**\1**', markdown, flags=re.IGNORECASE | re.DOTALL)
        
        # 移除其他 HTML 标签
        markdown = re.sub(r'<[^>]+>', '', markdown)
        
        # 清理多余的空行
        markdown = re.sub(r'\n{3,}', '\n\n', markdown)
        
        return markdown.strip()
    
    def close(self):
        """关闭客户端"""
        if hasattr(self, 'client'):
            try:
                self.client.close()
            except:
                pass


def read_csv_file(csv_file: str) -> List[Dict[str, str]]:
    """
    读取 CSV 文件
    
    Args:
        csv_file: CSV 文件路径
    
    Returns:
        数据行列表
    """
    rows = []
    try:
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # 只保留有 markText 的行
                if row.get('markText', '').strip():
                    rows.append(row)
        return rows
    except Exception as e:
        print(f"错误：读取 CSV 文件失败: {e}")
        return []


def group_by_chapters(rows: List[Dict[str, str]]) -> Dict[int, List[Dict[str, str]]]:
    """
    按章节分组
    
    Args:
        rows: CSV 数据行列表
    
    Returns:
        按 chapterUid 分组的字典
    """
    chapters = defaultdict(list)
    
    for row in rows:
        chapter_uid = row.get('chapterUid', '').strip()
        if chapter_uid:
            try:
                uid = int(chapter_uid)
                chapters[uid].append(row)
            except (ValueError, TypeError):
                continue
    
    return dict(sorted(chapters.items()))


def process_csv_file(csv_file: str, output_file: Optional[str] = None, api_key: Optional[str] = None, role: str = "学习者"):
    """
    处理 CSV 文件，生成学习大纲
    
    Args:
        csv_file: 输入的 CSV 文件路径
        output_file: 输出的 Markdown 文件路径，如果为 None 则自动生成
        api_key: Gemini API 密钥
        role: 角色（默认为"学习者"）
    """
    # 读取 CSV 文件
    print(f"正在读取文件: {csv_file}")
    rows = read_csv_file(csv_file)
    
    if not rows:
        print("错误：文件中没有有效数据")
        return
    
    print(f"共读取 {len(rows)} 行数据")
    
    # 获取领域和书籍信息
    field = ''
    book_title = ''
    for row in rows:
        if not field:
            field = row.get('categories', '').strip()
        if not book_title:
            book_title = row.get('title', '').strip()
        if field and book_title:
            break
    
    if not field:
        field = "未知领域"
    if not book_title:
        book_title = "未知书籍"
    
    print(f"书籍: {book_title}")
    print(f"领域: {field}\n")
    
    # 按章节分组
    print("正在按章节分组...")
    chapters_dict = group_by_chapters(rows)
    chapter_uids = sorted(chapters_dict.keys())
    
    print(f"共 {len(chapter_uids)} 个章节: {chapter_uids}\n")
    
    # 初始化生成器
    generator = OutlineGenerator(api_key=api_key, role=role)
    
    # 每3个章节为一组处理
    group_size = 3
    total_groups = (len(chapter_uids) + group_size - 1) // group_size
    
    print("=" * 60)
    print(f"开始处理，共 {total_groups} 组（每组 {group_size} 个章节）")
    print("=" * 60)
    
    all_markdown_parts = []
    all_html_parts = []
    
    for group_idx in range(total_groups):
        start_idx = group_idx * group_size
        end_idx = min(start_idx + group_size, len(chapter_uids))
        group_chapters = chapter_uids[start_idx:end_idx]
        
        print(f"\n[组 {group_idx + 1}/{total_groups}] 处理章节: {group_chapters}")
        
        # 收集这组章节的划线笔记和点评笔记
        mark_notes_parts = []  # 划线笔记（包含章节标题和划线文本）
        review_notes_parts = []  # 点评笔记
        
        chapter_names = []
        
        for chapter_uid in group_chapters:
            chapter_rows = chapters_dict[chapter_uid]
            chapter_name = chapter_rows[0].get('chapterName', f'章节{chapter_uid}') if chapter_rows else f'章节{chapter_uid}'
            chapter_names.append(chapter_name)
            
            # 按 createTime 排序，确保顺序
            chapter_rows_sorted = sorted(chapter_rows, key=lambda x: int(x.get('createTime', 0)) if x.get('createTime', '').strip().isdigit() else 0)
            
            # 添加章节标题（没有 bullet point）
            mark_notes_parts.append(chapter_name)
            
            # 收集划线笔记（有 bullet point）
            for row in chapter_rows_sorted:
                mark_text = row.get('markText', '').strip()
                if mark_text:
                    mark_notes_parts.append(f"- {mark_text}")
                
                # 收集点评笔记
                review_content = row.get('reviewContent', '').strip()
                if review_content:
                    review_notes_parts.append("【原文】：" + mark_text + "【点评】：" + review_content)
        
        if not mark_notes_parts:
            print(f"  跳过空组")
            continue
        
        # 格式化划线笔记（章节标题和划线文本，用空行分隔）
        mark_notes_text = "\n\n".join(mark_notes_parts)
        
        # 格式化点评笔记（用空行分隔）
        review_notes_text = "\n\n".join(review_notes_parts) if review_notes_parts else "无点评笔记"
        
        print(f"  章节名称: {', '.join(chapter_names)}")
        print(f"  划线笔记数: {len([p for p in mark_notes_parts if p.startswith('-')])}")
        print(f"  点评笔记数: {len(review_notes_parts)}")
        print(f"  正在生成大纲...")
        
        # 生成大纲（返回字典，包含 markdown 和 html）
        outline_result = generator.generate_outline(mark_notes_text, review_notes_text)
        
        # 添加组标题
        group_title_md = f"# 第 {group_idx + 1} 组：章节 {group_chapters[0]}-{group_chapters[-1]}\n\n"
        group_title_md += f"**章节名称**: {', '.join(chapter_names)}\n\n"
        group_title_md += f"**章节ID**: {', '.join(map(str, group_chapters))}\n\n"
        group_title_md += "---\n\n"
        
        group_title_html = f"<h1>第 {group_idx + 1} 组：章节 {group_chapters[0]}-{group_chapters[-1]}</h1>\n"
        group_title_html += f"<p><strong>章节名称</strong>: {', '.join(chapter_names)}</p>\n"
        group_title_html += f"<p><strong>章节ID</strong>: {', '.join(map(str, group_chapters))}</p>\n"
        group_title_html += "<hr>\n"
        
        # 添加到总列表
        all_markdown_parts.append(group_title_md + outline_result.get('markdown', ''))
        all_html_parts.append(group_title_html + outline_result.get('html', ''))
        
        print(f"  ✓ 完成")
        
        # 添加延迟，避免 API 请求过快
        if group_idx < total_groups - 1:
            time.sleep(0.5)
    
    # 关闭客户端
    generator.close()
    
    # 合并所有大纲
    final_markdown = f"# {book_title} - 学习大纲\n\n"
    final_markdown += f"**领域**: {field}\n\n"
    final_markdown += "---\n\n"
    final_markdown += "\n\n".join(all_markdown_parts)
    
    # 清理 HTML 中可能残留的 Markdown 代码块语法
    cleaned_html_parts = []
    for html_part in all_html_parts:
        # 移除 Markdown 代码块标记（但保留 HTML 标签内的内容）
        cleaned = re.sub(r'```[a-z]*\n?', '', html_part)
        cleaned = re.sub(r'\n?```', '', cleaned)
        cleaned_html_parts.append(cleaned)
    
    final_html = f"<html><head><meta charset='utf-8'><title>{book_title} - 学习大纲</title></head><body>\n"
    final_html += f"<h1>{book_title} - 学习大纲</h1>\n"
    final_html += f"<p><strong>领域</strong>: {field}</p>\n"
    final_html += "<hr>\n"
    final_html += "\n".join(cleaned_html_parts)
    final_html += "</body></html>"
    
    # 生成输出文件名
    if output_file is None:
        input_path = Path(csv_file)
        script_dir = Path(__file__).parent  # llm 目录
        output_dir = script_dir / "outlines"
        output_dir.mkdir(parents=True, exist_ok=True)
        base_name = input_path.stem
        markdown_file = str(output_dir / f"{base_name}_outline.md")
        html_file = str(output_dir / f"{base_name}_outline.html")
    else:
        # 如果指定了输出文件，使用它作为基础名称
        output_path = Path(output_file)
        base_name = output_path.stem
        output_dir = output_path.parent
        markdown_file = str(output_dir / f"{base_name}.md")
        html_file = str(output_dir / f"{base_name}.html")
    
    print(f"\n正在保存文件...")
    
    # 保存 Markdown 文件
    markdown_path = Path(markdown_file)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    with open(markdown_path, 'w', encoding='utf-8') as f:
        f.write(final_markdown)
    print(f"✓ Markdown 已保存到: {markdown_file}")
    
    # 保存 HTML 文件
    html_path = Path(html_file)
    html_path.parent.mkdir(parents=True, exist_ok=True)
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(final_html)
    print(f"✓ HTML 已保存到: {html_file}")


def main():
    """主函数"""
    # 获取 API key
    api_key = os.environ.get('GOOGLE_API_KEY') or os.environ.get('GEMINI_API_KEY')
    
    # 获取命令行参数
    if len(sys.argv) < 2:
        print("使用方法：")
        print("  python generate_outline.py <输入CSV文件> [输出Markdown文件] [角色] [api_key]")
        print("\n示例：")
        print("  python generate_outline.py output/notes/3300064831.csv")
        print("  python generate_outline.py output/notes/3300064831.csv output/outline.md")
        print("  python generate_outline.py output/notes/3300064831.csv output/outline.md 学习者")
        print("\n环境变量：")
        print("  export GEMINI_API_KEY='your_api_key'")
        print("  export GOOGLE_API_KEY='your_api_key'")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    role = sys.argv[3] if len(sys.argv) > 3 else "学习者"
    
    if len(sys.argv) > 4:
        api_key = sys.argv[4]
    
    if not api_key:
        print("错误：请提供 Gemini API 密钥")
        print("可以通过环境变量 GEMINI_API_KEY 或 GOOGLE_API_KEY 设置")
        sys.exit(1)
    
    if not os.path.exists(input_file):
        print(f"错误：文件不存在: {input_file}")
        sys.exit(1)
    
    try:
        process_csv_file(input_file, output_file, api_key, role)
    except KeyboardInterrupt:
        print("\n\n用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n错误：{e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

