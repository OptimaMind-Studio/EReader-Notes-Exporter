#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EReader Notes Exporter Web UI
微信读书笔记导出工具 Web 图形界面
"""

from flask import Flask, render_template_string, request, jsonify, send_file
import subprocess
import sys
import os
import threading
import json
from pathlib import Path
from datetime import datetime
import webbrowser
import time


app = Flask(__name__)

# 获取项目根目录
PROJECT_ROOT = Path(__file__).parent.parent

# 全局状态
execution_status = {
    'running': False,
    'current_task': None,
    'logs': [],
    'max_logs': 1000
}


# HTML 模板
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>微信读书笔记导出工具</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 10px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
            overflow: hidden;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }
        .header h1 {
            font-size: 28px;
            margin-bottom: 10px;
        }
        .content {
            padding: 30px;
        }
        .section {
            margin-bottom: 30px;
            padding: 20px;
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            background: #f9f9f9;
        }
        .section h2 {
            color: #333;
            margin-bottom: 15px;
            font-size: 18px;
            border-bottom: 2px solid #667eea;
            padding-bottom: 10px;
        }
        .form-group {
            margin-bottom: 15px;
        }
        label {
            display: block;
            margin-bottom: 5px;
            color: #555;
            font-weight: 500;
        }
        input[type="text"], input[type="file"] {
            width: 100%;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 5px;
            font-size: 14px;
        }
        .button-group {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 10px;
            margin-top: 15px;
        }
        button {
            padding: 12px 20px;
            border: none;
            border-radius: 5px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            font-size: 14px;
            cursor: pointer;
            transition: all 0.3s;
            font-weight: 500;
        }
        button:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
        }
        button:disabled {
            background: #ccc;
            cursor: not-allowed;
            transform: none;
        }
        .log-container {
            background: #1e1e1e;
            color: #d4d4d4;
            padding: 20px;
            border-radius: 5px;
            height: 400px;
            overflow-y: auto;
            font-family: 'Courier New', monospace;
            font-size: 12px;
            line-height: 1.6;
        }
        .log-entry {
            margin-bottom: 5px;
        }
        .log-time {
            color: #858585;
        }
        .log-info {
            color: #4ec9b0;
        }
        .log-success {
            color: #4ec9b0;
        }
        .log-error {
            color: #f48771;
        }
        .status-bar {
            padding: 15px;
            background: #f0f0f0;
            border-top: 1px solid #e0e0e0;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .status {
            font-weight: 500;
            color: #333;
        }
        .status.running {
            color: #667eea;
        }
        .status.error {
            color: #f48771;
        }
        .status.success {
            color: #4ec9b0;
        }
        .cookie-editor {
            width: 100%;
            height: 200px;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 5px;
            font-family: monospace;
            font-size: 12px;
        }
        .grid-2 {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
        }
        @media (max-width: 768px) {
            .grid-2 {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📚 微信读书笔记导出工具</h1>
            <p>WeRead Notes Exporter</p>
        </div>
        
        <div class="content">
            <!-- Cookie 设置 -->
            <div class="section">
                <h2>🔐 Cookie 设置</h2>
                <div class="form-group">
                    <label>Cookie 文件路径:</label>
                    <input type="text" id="cookiePath" value="{{ cookie_path }}" readonly>
                </div>
                <div class="button-group">
                    <button onclick="browseCookie()">浏览文件</button>
                    <button onclick="editCookie()">编辑 Cookie</button>
                </div>
            </div>
            
            <!-- 书籍选择 -->
            <div class="section">
                <h2>📖 书籍选择（可选）</h2>
                <div class="grid-2">
                    <div class="form-group">
                        <label>书籍ID:</label>
                        <input type="text" id="bookId" placeholder="例如: 3300089819">
                    </div>
                    <div class="form-group">
                        <label>或书名:</label>
                        <input type="text" id="bookName" placeholder="例如: 极简央行课">
                    </div>
                </div>
            </div>
            
            <!-- WeRead 功能 -->
            <div class="section">
                <h2>📥 WeRead 数据获取</h2>
                <div class="button-group">
                    <button onclick="runCommand('fetch')">获取书籍列表</button>
                    <button onclick="runCommand('fetch')">获取书签和点评</button>
                </div>
            </div>
            
            <!-- LLM 功能 -->
            <div class="section">
                <h2>🤖 LLM 处理</h2>
                <div class="button-group">
                    <button onclick="runCommand('extract_concepts')">提取概念并导入 Anki</button>
                    <button onclick="runCommand('generate_outline')">生成大纲</button>
                    <button onclick="runCommand('generate_guidebook')">生成 Guidebook</button>
                    <button onclick="runCommand('llm')">完整 LLM 流程</button>
                </div>
            </div>
            
            <!-- Anki 导入 -->
            <div class="section">
                <h2>📦 Anki 导入</h2>
                <div class="button-group">
                    <button onclick="runCommand('import_concepts_to_anki')">导入 Concepts 到 Anki</button>
                    <button onclick="runCommand('import_guidebook_to_anki')">导入 Guidebook 到 Anki</button>
                </div>
            </div>
            
            <!-- 自动化流程 -->
            <div class="section">
                <h2>⚡ 自动化流程</h2>
                <div class="button-group">
                    <button onclick="runCommand('concepts_pipeline')">
                        Concepts 完整流程 (Fetch + Extract Concepts)
                    </button>
                    <button onclick="runCommand('guidebook_pipeline')">
                        Guidebook 完整流程 (Fetch + Generate + Anki)
                    </button>
                </div>
            </div>
            
            <!-- 日志输出 -->
            <div class="section">
                <h2>📋 日志输出</h2>
                <div class="log-container" id="logContainer">
                    <div class="log-entry">
                        <span class="log-time">[系统]</span>
                        <span class="log-info">就绪，等待操作...</span>
                    </div>
                </div>
                <div style="margin-top: 10px;">
                    <button onclick="clearLogs()">清空日志</button>
                </div>
            </div>
        </div>
        
        <div class="status-bar">
            <div>
                <span class="status" id="status">就绪</span>
            </div>
            <div>
                <span id="currentTask"></span>
            </div>
        </div>
    </div>
    
    <script>
        let logPolling = null;
        
        function addLog(message, type = 'info') {
            const container = document.getElementById('logContainer');
            const entry = document.createElement('div');
            entry.className = 'log-entry';
            const time = new Date().toLocaleTimeString();
            entry.innerHTML = `<span class="log-time">[${time}]</span> <span class="log-${type}">${escapeHtml(message)}</span>`;
            container.appendChild(entry);
            container.scrollTop = container.scrollHeight;
        }
        
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
        
        function updateStatus(status, task = '') {
            document.getElementById('status').textContent = status;
            document.getElementById('status').className = 'status ' + (status.includes('错误') ? 'error' : status.includes('完成') ? 'success' : status.includes('执行') ? 'running' : '');
            document.getElementById('currentTask').textContent = task;
        }
        
        function browseCookie() {
            // 简化版：直接编辑路径
            const path = prompt('请输入 Cookie 文件路径:', document.getElementById('cookiePath').value);
            if (path) {
                document.getElementById('cookiePath').value = path;
                fetch('/api/update_cookie_path', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({path: path})
                });
            }
        }
        
        function editCookie() {
            window.open('/cookie_editor', '_blank', 'width=800,height=600');
        }
        
        function runCommand(commandType) {
            const bookId = document.getElementById('bookId').value.trim();
            const bookName = document.getElementById('bookName').value.trim();
            
            updateStatus('执行中...', commandType);
            addLog(`开始执行: ${commandType}`, 'info');
            
            fetch('/api/run_command', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    command_type: commandType,
                    book_id: bookId || null,
                    book_name: bookName || null
                })
            }).then(response => response.json())
            .then(data => {
                if (data.success) {
                    updateStatus('完成', '');
                    addLog(`✓ ${commandType} 执行完成`, 'success');
                    startLogPolling();
                } else {
                    updateStatus('错误', '');
                    addLog(`✗ ${commandType} 执行失败: ${data.error}`, 'error');
                }
            });
        }
        
        function startLogPolling() {
            if (logPolling) clearInterval(logPolling);
            logPolling = setInterval(() => {
                fetch('/api/get_logs')
                    .then(response => response.json())
                    .then(data => {
                        if (data.logs && data.logs.length > 0) {
                            const container = document.getElementById('logContainer');
                            const currentLength = container.children.length;
                            data.logs.slice(currentLength).forEach(log => {
                                addLog(log.message, log.type || 'info');
                            });
                        }
                        if (data.status) {
                            updateStatus(data.status, data.current_task || '');
                        }
                    });
            }, 500);
        }
        
        function clearLogs() {
            document.getElementById('logContainer').innerHTML = '';
            fetch('/api/clear_logs', {method: 'POST'});
        }
        
        // 页面加载时开始轮询日志
        window.onload = function() {
            startLogPolling();
        };
    </script>
</body>
</html>
"""


@app.route('/')
def index():
    """主页面"""
    cookie_path = str(PROJECT_ROOT / "wereader" / "cookies.txt")
    return render_template_string(HTML_TEMPLATE, cookie_path=cookie_path)


@app.route('/api/run_command', methods=['POST'])
def api_run_command():
    """执行命令 API"""
    data = request.json
    command_type = data.get('command_type')
    book_id = data.get('book_id')
    book_name = data.get('book_name')
    
    if execution_status['running']:
        return jsonify({'success': False, 'error': '已有任务正在执行中'})
    
    # 在新线程中执行命令
    thread = threading.Thread(
        target=_run_command_thread,
        args=(command_type, book_id, book_name)
    )
    thread.daemon = True
    thread.start()
    
    return jsonify({'success': True})


@app.route('/api/get_logs', methods=['GET'])
def api_get_logs():
    """获取日志 API"""
    return jsonify({
        'logs': execution_status['logs'],
        'status': execution_status.get('status', '就绪'),
        'current_task': execution_status.get('current_task', '')
    })


@app.route('/api/clear_logs', methods=['POST'])
def api_clear_logs():
    """清空日志 API"""
    execution_status['logs'] = []
    return jsonify({'success': True})


@app.route('/api/update_cookie_path', methods=['POST'])
def api_update_cookie_path():
    """更新 Cookie 路径 API"""
    data = request.json
    # 这里可以保存到配置文件
    return jsonify({'success': True})


@app.route('/cookie_editor')
def cookie_editor():
    """Cookie 编辑器页面"""
    cookie_path = PROJECT_ROOT / "wereader" / "cookies.txt"
    try:
        with open(cookie_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except:
        content = ""
    
    editor_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>编辑 Cookie</title>
        <style>
            body {{
                font-family: monospace;
                padding: 20px;
                background: #f5f5f5;
            }}
            .container {{
                max-width: 900px;
                margin: 0 auto;
                background: white;
                padding: 20px;
                border-radius: 5px;
            }}
            textarea {{
                width: 100%;
                height: 500px;
                padding: 10px;
                border: 1px solid #ddd;
                border-radius: 5px;
                font-family: monospace;
                font-size: 12px;
            }}
            button {{
                margin-top: 10px;
                padding: 10px 20px;
                background: #667eea;
                color: white;
                border: none;
                border-radius: 5px;
                cursor: pointer;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h2>编辑 Cookie 文件</h2>
            <p>文件路径: {cookie_path}</p>
            <textarea id="cookieContent">{content}</textarea>
            <button onclick="saveCookie()">保存</button>
            <button onclick="window.close()">取消</button>
        </div>
        <script>
            function saveCookie() {{
                const content = document.getElementById('cookieContent').value;
                fetch('/api/save_cookie', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{content: content}})
                }}).then(response => response.json())
                .then(data => {{
                    if (data.success) {{
                        alert('保存成功！');
                        window.close();
                    }} else {{
                        alert('保存失败: ' + data.error);
                    }}
                }});
            }}
        </script>
    </body>
    </html>
    """
    return editor_html


@app.route('/api/save_cookie', methods=['POST'])
def api_save_cookie():
    """保存 Cookie API"""
    data = request.json
    content = data.get('content', '')
    cookie_path = PROJECT_ROOT / "wereader" / "cookies.txt"
    
    try:
        cookie_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cookie_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


def _add_log(message, log_type='info'):
    """添加日志"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = {
        'time': timestamp,
        'message': message,
        'type': log_type
    }
    execution_status['logs'].append(log_entry)
    # 限制日志数量
    if len(execution_status['logs']) > execution_status['max_logs']:
        execution_status['logs'] = execution_status['logs'][-execution_status['max_logs']:]


def _run_command_thread(command_type, book_id, book_name):
    """在后台线程中运行命令"""
    execution_status['running'] = True
    execution_status['current_task'] = command_type
    execution_status['status'] = f'正在执行: {command_type}...'
    
    try:
        if command_type == "fetch":
            _run_fetch(book_id)
        elif command_type == "extract_concepts":
            _run_extract_concepts(book_id, book_name)
        elif command_type == "generate_outline":
            _run_generate_outline(book_id, book_name)
        elif command_type == "generate_guidebook":
            _run_generate_guidebook(book_id, book_name)
        elif command_type == "llm":
            _run_llm(book_id, book_name)
        elif command_type == "import_concepts_to_anki":
            _run_import_concepts_to_anki(book_id, book_name)
        elif command_type == "import_guidebook_to_anki":
            _run_import_guidebook_to_anki(book_id, book_name)
        elif command_type == "concepts_pipeline":
            _run_concepts_pipeline(book_id, book_name)
        elif command_type == "guidebook_pipeline":
            _run_guidebook_pipeline(book_id, book_name)
        
        execution_status['status'] = '完成'
        _add_log(f"✓ {command_type} 执行完成", 'success')
        
    except Exception as e:
        execution_status['status'] = '错误'
        _add_log(f"✗ 执行失败: {e}", 'error')
    finally:
        execution_status['running'] = False
        execution_status['current_task'] = None


def _run_fetch(book_id):
    """运行 fetch 命令"""
    script_path = PROJECT_ROOT / "wereader" / "fetch.py"
    args = []
    if book_id:
        args.extend(['--book-id', book_id])
    _run_script(script_path, args)


def _run_extract_concepts(book_id, book_name):
    """运行提取概念命令（包含导入到 Anki）"""
    # 步骤 1: 提取概念
    script_path = PROJECT_ROOT / "llm" / "scripts" / "extract_concepts.py"
    args = []
    if book_id:
        args.extend(['--book-id', book_id])
    elif book_name:
        args.extend(['--title', book_name])
    else:
        raise ValueError("提取概念需要指定书籍ID或书名")
    _run_script(script_path, args)
    
    # 步骤 2: 导入到 Anki
    _add_log("概念提取完成，开始导入到 Anki...", 'info')
    _run_import_concepts_to_anki(book_id, book_name)


def _run_generate_outline(book_id, book_name):
    """运行生成大纲命令"""
    script_path = PROJECT_ROOT / "llm" / "scripts" / "generate_outline.py"
    args = []
    if book_id:
        args.extend(['--book-id', book_id])
    elif book_name:
        args.extend(['--title', book_name])
    else:
        raise ValueError("生成大纲需要指定书籍ID或书名")
    _run_script(script_path, args)


def _run_generate_guidebook(book_id, book_name):
    """运行生成 Guidebook 命令"""
    script_path = PROJECT_ROOT / "llm" / "scripts" / "generate_guidebook.py"
    args = []
    if book_id:
        args.extend(['--book-id', book_id])
    elif book_name:
        args.extend(['--title', book_name])
    else:
        raise ValueError("生成 Guidebook 需要指定书籍ID或书名")
    _run_script(script_path, args)


def _run_llm(book_id, book_name):
    """运行完整 LLM 流程"""
    script_path = PROJECT_ROOT / "llm" / "llm.py"
    args = []
    if book_id:
        args.extend(['--book-id', book_id])
    elif book_name:
        args.extend(['--title', book_name])
    else:
        raise ValueError("LLM 流程需要指定书籍ID或书名")
    _run_script(script_path, args)


def _run_import_concepts_to_anki(book_id, book_name):
    """运行导入 Concepts 到 Anki"""
    script_path = PROJECT_ROOT / "anki" / "scripts" / "import_concepts_to_anki.py"
    args = ['--sync']  # 默认同步到 AnkiWeb
    if book_id:
        args.extend(['--book-id', book_id])
    elif book_name:
        args.extend(['--book-name', book_name])
    _run_script(script_path, args)


def _run_import_guidebook_to_anki(book_id, book_name):
    """运行导入 Guidebook 到 Anki"""
    script_path = PROJECT_ROOT / "anki" / "scripts" / "import_guidebook_to_anki.py"
    args = ['--sync']  # 默认同步到 AnkiWeb
    if book_id:
        args.extend(['--book-id', book_id])
    elif book_name:
        args.extend(['--book-name', book_name])
    _run_script(script_path, args)


def _run_concepts_pipeline(book_id, book_name):
    """运行 Concepts 完整流程"""
    script_path = PROJECT_ROOT / "workflow" / "concepts_pipeline.py"
    args = []
    if book_id:
        args.extend(['--book-id', book_id])
    elif book_name:
        args.extend(['--book-name', book_name])
    _run_script(script_path, args)


def _run_guidebook_pipeline(book_id, book_name):
    """运行 Guidebook 完整流程"""
    script_path = PROJECT_ROOT / "workflow" / "guidebook_pipeline.py"
    args = []
    if book_id:
        args.extend(['--book-id', book_id])
    elif book_name:
        args.extend(['--book-name', book_name])
    _run_script(script_path, args)


def _run_script(script_path, args):
    """运行脚本并捕获输出"""
    if not script_path.exists():
        raise FileNotFoundError(f"脚本不存在: {script_path}")
    
    _add_log(f"开始执行: {script_path.name}")
    _add_log(f"参数: {' '.join(args) if args else '无'}")
    _add_log("-" * 60)
    
    try:
        process = subprocess.Popen(
            [sys.executable, str(script_path)] + args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True,
            cwd=str(PROJECT_ROOT),
            env=os.environ.copy()
        )
        
        # 实时读取输出
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                _add_log(output.rstrip(), 'info')
        
        process.wait()
        
        if process.returncode != 0:
            _add_log(f"✗ 脚本执行失败，退出码: {process.returncode}", 'error')
        else:
            _add_log("✓ 脚本执行成功", 'success')
            
    except Exception as e:
        _add_log(f"✗ 执行出错: {e}", 'error')
        raise


def main():
    """主函数"""
    print("=" * 60)
    print("微信读书笔记导出工具 Web UI")
    print("=" * 60)
    print(f"\n正在启动 Web 服务器...")
    print(f"访问地址: http://127.0.0.1:5000")
    print(f"\n按 Ctrl+C 停止服务器\n")
    
    # 延迟打开浏览器
    def open_browser():
        time.sleep(1.5)
        webbrowser.open('http://127.0.0.1:5000')
    
    threading.Thread(target=open_browser, daemon=True).start()
    
    # 启动 Flask 应用
    app.run(host='127.0.0.1', port=5000, debug=False)


if __name__ == "__main__":
    main()

