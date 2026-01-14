#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EReader Notes Exporter GUI
微信读书笔记导出工具图形界面
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import subprocess
import sys
import os
import threading
from pathlib import Path
from datetime import datetime


class EReaderApp:
    """微信读书笔记导出工具主应用"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("微信读书笔记导出工具")
        self.root.geometry("900x700")
        
        # 获取项目根目录
        self.project_root = Path(__file__).parent.parent
        
        # 设置样式
        style = ttk.Style()
        style.theme_use('clam')
        
        # 创建主框架
        self.setup_ui()
        
        # 加载 cookie 文件路径
        self.cookie_file = self.project_root / "wereader" / "cookies.txt"
        
    def setup_ui(self):
        """设置用户界面"""
        # 主容器
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 配置网格权重
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(2, weight=1)
        
        # 标题
        title_label = ttk.Label(main_frame, text="微信读书笔记导出工具", 
                               font=("Arial", 16, "bold"))
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 20))
        
        # Cookie 设置区域
        cookie_frame = ttk.LabelFrame(main_frame, text="Cookie 设置", padding="10")
        cookie_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        cookie_frame.columnconfigure(1, weight=1)
        
        ttk.Label(cookie_frame, text="Cookie 文件:").grid(row=0, column=0, padx=(0, 10))
        self.cookie_path_var = tk.StringVar(value=str(self.project_root / "wereader" / "cookies.txt"))
        cookie_entry = ttk.Entry(cookie_frame, textvariable=self.cookie_path_var, width=50)
        cookie_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 10))
        
        ttk.Button(cookie_frame, text="浏览", command=self.browse_cookie_file).grid(row=0, column=2)
        ttk.Button(cookie_frame, text="编辑 Cookie", command=self.edit_cookie).grid(row=0, column=3, padx=(10, 0))
        
        # 功能按钮区域
        buttons_frame = ttk.LabelFrame(main_frame, text="功能", padding="10")
        buttons_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        buttons_frame.columnconfigure(0, weight=1)
        buttons_frame.columnconfigure(1, weight=1)
        
        # WeRead 功能按钮
        wereader_frame = ttk.LabelFrame(buttons_frame, text="WeRead 数据获取", padding="10")
        wereader_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N), padx=(0, 5))
        
        ttk.Button(wereader_frame, text="获取书籍列表", 
                  command=lambda: self.run_command("fetch", None)).pack(fill=tk.X, pady=2)
        ttk.Button(wereader_frame, text="获取书签和点评", 
                  command=lambda: self.run_command("fetch", None)).pack(fill=tk.X, pady=2)
        
        # LLM 功能按钮
        llm_frame = ttk.LabelFrame(buttons_frame, text="LLM 处理", padding="10")
        llm_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N), padx=(5, 0))
        
        ttk.Button(llm_frame, text="提取概念并导入 Anki", 
                  command=lambda: self.run_command("extract_concepts", None)).pack(fill=tk.X, pady=2)
        ttk.Button(llm_frame, text="生成大纲", 
                  command=lambda: self.run_command("generate_outline", None)).pack(fill=tk.X, pady=2)
        ttk.Button(llm_frame, text="生成 Guidebook", 
                  command=lambda: self.run_command("generate_guidebook", None)).pack(fill=tk.X, pady=2)
        ttk.Button(llm_frame, text="完整 LLM 流程", 
                  command=lambda: self.run_command("llm", None)).pack(fill=tk.X, pady=2)
        
        # Anki 导入按钮
        anki_frame = ttk.LabelFrame(buttons_frame, text="Anki 导入", padding="10")
        anki_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 0))
        
        ttk.Button(anki_frame, text="导入 Concepts 到 Anki", 
                  command=lambda: self.run_command("import_concepts_to_anki", None)).pack(fill=tk.X, pady=2)
        ttk.Button(anki_frame, text="导入 Guidebook 到 Anki", 
                  command=lambda: self.run_command("import_guidebook_to_anki", None)).pack(fill=tk.X, pady=2)
        
        # 自动化流程按钮
        auto_frame = ttk.LabelFrame(buttons_frame, text="自动化流程", padding="10")
        auto_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 0))
        
        ttk.Button(auto_frame, text="Concepts 完整流程 (Fetch + Extract Concepts)", 
                  command=lambda: self.run_command("concepts_pipeline", None)).pack(fill=tk.X, pady=2)
        ttk.Button(auto_frame, text="Guidebook 完整流程 (Fetch + Generate + Anki)", 
                  command=lambda: self.run_command("guidebook_pipeline", None)).pack(fill=tk.X, pady=2)
        
        # 书籍输入区域
        book_input_frame = ttk.LabelFrame(buttons_frame, text="书籍选择（可选）", padding="10")
        book_input_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 0))
        
        ttk.Label(book_input_frame, text="书籍ID:").grid(row=0, column=0, padx=(0, 10))
        self.book_id_var = tk.StringVar()
        book_id_entry = ttk.Entry(book_input_frame, textvariable=self.book_id_var, width=20)
        book_id_entry.grid(row=0, column=1, padx=(0, 20))
        
        ttk.Label(book_input_frame, text="或书名:").grid(row=0, column=2, padx=(0, 10))
        self.book_name_var = tk.StringVar()
        book_name_entry = ttk.Entry(book_input_frame, textvariable=self.book_name_var, width=20)
        book_name_entry.grid(row=0, column=3)
        
        # 日志输出区域
        log_frame = ttk.LabelFrame(main_frame, text="日志输出", padding="10")
        log_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=15, wrap=tk.WORD)
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 清空日志按钮
        ttk.Button(log_frame, text="清空日志", command=self.clear_log).grid(row=1, column=0, pady=(10, 0))
        
        # 状态栏
        self.status_var = tk.StringVar(value="就绪")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN)
        status_bar.grid(row=5, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 0))
        
    def browse_cookie_file(self):
        """浏览选择 Cookie 文件"""
        filename = filedialog.askopenfilename(
            title="选择 Cookie 文件",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if filename:
            self.cookie_path_var.set(filename)
            self.cookie_file = Path(filename)
    
    def edit_cookie(self):
        """编辑 Cookie 文件"""
        cookie_path = Path(self.cookie_path_var.get())
        
        # 如果文件不存在，创建它
        if not cookie_path.exists():
            cookie_path.parent.mkdir(parents=True, exist_ok=True)
            cookie_path.touch()
        
        # 打开编辑对话框
        dialog = CookieEditorDialog(self.root, cookie_path)
        self.root.wait_window(dialog.dialog)
    
    def log(self, message):
        """添加日志消息"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.root.update_idletasks()
    
    def clear_log(self):
        """清空日志"""
        self.log_text.delete(1.0, tk.END)
    
    def run_command(self, command_type, book_id=None):
        """运行命令"""
        if command_type == "fetch" or command_type == "concepts_pipeline" or command_type == "guidebook_pipeline":
            # Fetch 和 pipeline 需要 Cookie
            if not Path(self.cookie_path_var.get()).exists():
                messagebox.showerror("错误", "Cookie 文件不存在，请先设置 Cookie 文件")
                return
        
        # 获取书籍ID或书名
        book_id = self.book_id_var.get().strip() or None
        book_name = self.book_name_var.get().strip() or None
        
        # 在新线程中运行命令，避免阻塞 UI
        thread = threading.Thread(target=self._run_command_thread, args=(command_type, book_id, book_name))
        thread.daemon = True
        thread.start()
    
    def _run_command_thread(self, command_type, book_id, book_name):
        """在后台线程中运行命令"""
        try:
            self.status_var.set(f"正在执行: {command_type}...")
            
            if command_type == "fetch":
                self._run_fetch(book_id)
            elif command_type == "extract_concepts":
                self._run_extract_concepts(book_id, book_name)
            elif command_type == "generate_outline":
                self._run_generate_outline(book_id, book_name)
            elif command_type == "generate_guidebook":
                self._run_generate_guidebook(book_id, book_name)
            elif command_type == "llm":
                self._run_llm(book_id, book_name)
            elif command_type == "import_concepts_to_anki":
                self._run_import_concepts_to_anki(book_id, book_name)
            elif command_type == "import_guidebook_to_anki":
                self._run_import_guidebook_to_anki(book_id, book_name)
            elif command_type == "concepts_pipeline":
                self._run_concepts_pipeline(book_id, book_name)
            elif command_type == "guidebook_pipeline":
                self._run_guidebook_pipeline(book_id, book_name)
            
            self.status_var.set("完成")
            self.log(f"✓ {command_type} 执行完成")
            
        except Exception as e:
            self.status_var.set("错误")
            self.log(f"✗ 执行失败: {e}")
            messagebox.showerror("错误", f"执行失败: {e}")
    
    def _run_fetch(self, book_id):
        """运行 fetch 命令"""
        script_path = self.project_root / "wereader" / "fetch.py"
        args = []
        if book_id:
            args.extend(['--book-id', book_id])
        
        self._run_script(script_path, args)
    
    def _run_extract_concepts(self, book_id, book_name):
        """运行提取概念命令（包含导入到 Anki）"""
        # 步骤 1: 提取概念
        script_path = self.project_root / "llm" / "scripts" / "extract_concepts.py"
        args = []
        if book_id:
            args.extend(['--book-id', book_id])
        elif book_name:
            args.extend(['--title', book_name])
        else:
            messagebox.showwarning("警告", "提取概念需要指定书籍ID或书名")
            return
        
        self._run_script(script_path, args)
        
        # 步骤 2: 导入到 Anki
        self.log("概念提取完成，开始导入到 Anki...")
        self._run_import_concepts_to_anki(book_id, book_name)
    
    def _run_generate_outline(self, book_id, book_name):
        """运行生成大纲命令"""
        script_path = self.project_root / "llm" / "scripts" / "generate_outline.py"
        args = []
        if book_id:
            args.extend(['--book-id', book_id])
        elif book_name:
            args.extend(['--title', book_name])
        else:
            messagebox.showwarning("警告", "生成大纲需要指定书籍ID或书名")
            return
        
        self._run_script(script_path, args)
    
    def _run_generate_guidebook(self, book_id, book_name):
        """运行生成 Guidebook 命令"""
        script_path = self.project_root / "llm" / "scripts" / "generate_guidebook.py"
        args = []
        if book_id:
            args.extend(['--book-id', book_id])
        elif book_name:
            args.extend(['--title', book_name])
        else:
            messagebox.showwarning("警告", "生成 Guidebook 需要指定书籍ID或书名")
            return
        
        self._run_script(script_path, args)
    
    def _run_llm(self, book_id, book_name):
        """运行完整 LLM 流程"""
        script_path = self.project_root / "llm" / "llm.py"
        args = []
        if book_id:
            args.extend(['--book-id', book_id])
        elif book_name:
            args.extend(['--title', book_name])
        else:
            messagebox.showwarning("警告", "LLM 流程需要指定书籍ID或书名")
            return
        
        self._run_script(script_path, args)
    
    def _run_import_concepts_to_anki(self, book_id, book_name):
        """运行导入 Concepts 到 Anki"""
        script_path = self.project_root / "anki" / "scripts" / "import_concepts_to_anki.py"
        args = ['--sync']  # 默认同步到 AnkiWeb
        if book_id:
            args.extend(['--book-id', book_id])
        elif book_name:
            args.extend(['--book-name', book_name])
        
        self._run_script(script_path, args)
    
    def _run_import_guidebook_to_anki(self, book_id, book_name):
        """运行导入 Guidebook 到 Anki"""
        script_path = self.project_root / "anki" / "scripts" / "import_guidebook_to_anki.py"
        args = ['--sync']  # 默认同步到 AnkiWeb
        if book_id:
            args.extend(['--book-id', book_id])
        elif book_name:
            args.extend(['--book-name', book_name])
        
        self._run_script(script_path, args)
    
    def _run_concepts_pipeline(self, book_id, book_name):
        """运行 Concepts 完整流程"""
        script_path = self.project_root / "workflow" / "concepts_pipeline.py"
        args = []
        if book_id:
            args.extend(['--book-id', book_id])
        elif book_name:
            args.extend(['--book-name', book_name])
        
        self._run_script(script_path, args)
    
    def _run_guidebook_pipeline(self, book_id, book_name):
        """运行 Guidebook 完整流程"""
        script_path = self.project_root / "workflow" / "guidebook_pipeline.py"
        args = []
        if book_id:
            args.extend(['--book-id', book_id])
        elif book_name:
            args.extend(['--book-name', book_name])
        
        self._run_script(script_path, args)
    
    def _run_script(self, script_path, args):
        """运行脚本并捕获输出"""
        if not script_path.exists():
            raise FileNotFoundError(f"脚本不存在: {script_path}")
        
        self.log(f"开始执行: {script_path.name}")
        self.log(f"参数: {' '.join(args) if args else '无'}")
        self.log("-" * 60)
        
        try:
            # 运行脚本并实时捕获输出
            process = subprocess.Popen(
                [sys.executable, str(script_path)] + args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True,
                cwd=str(self.project_root),
                env=os.environ.copy()
            )
            
            # 实时读取输出
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    self.log(output.rstrip())
            
            process.wait()
            
            if process.returncode != 0:
                self.log(f"✗ 脚本执行失败，退出码: {process.returncode}")
            else:
                self.log("✓ 脚本执行成功")
                
        except Exception as e:
            self.log(f"✗ 执行出错: {e}")
            raise


class CookieEditorDialog:
    """Cookie 编辑对话框"""
    
    def __init__(self, parent, cookie_path):
        self.cookie_path = cookie_path
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("编辑 Cookie")
        self.dialog.geometry("800x600")
        
        # 读取现有内容
        try:
            with open(cookie_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except:
            content = ""
        
        # 创建文本编辑器
        ttk.Label(self.dialog, text=f"编辑 Cookie 文件: {cookie_path}", 
                 font=("Arial", 10, "bold")).pack(pady=10)
        
        text_frame = ttk.Frame(self.dialog, padding="10")
        text_frame.pack(fill=tk.BOTH, expand=True)
        
        self.text_editor = scrolledtext.ScrolledText(text_frame, wrap=tk.WORD)
        self.text_editor.pack(fill=tk.BOTH, expand=True)
        self.text_editor.insert(1.0, content)
        
        # 按钮
        button_frame = ttk.Frame(self.dialog, padding="10")
        button_frame.pack()
        
        ttk.Button(button_frame, text="保存", command=self.save).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="取消", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)
    
    def save(self):
        """保存 Cookie 文件"""
        content = self.text_editor.get(1.0, tk.END)
        try:
            with open(self.cookie_path, 'w', encoding='utf-8') as f:
                f.write(content.rstrip())
            messagebox.showinfo("成功", "Cookie 文件已保存")
            self.dialog.destroy()
        except Exception as e:
            messagebox.showerror("错误", f"保存失败: {e}")


def main():
    """主函数"""
    root = tk.Tk()
    app = EReaderApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

