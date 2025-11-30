from flask import Flask, jsonify, send_file
import socket
import os

app = Flask(__name__)

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip

@app.route('/', methods=['GET'])
def index():
    """Hiển thị các thư mục và file trong thư mục hiện tại"""
    try:
        current_dir = os.path.abspath('.')
        items = []
        for item in sorted(os.listdir('.')):
            item_path = os.path.join('.', item)
            if os.path.isdir(item_path):
                items.append({"name": item, "type": "dir"})
            else:
                items.append({"name": item, "type": "file"})
        
        current_dir_escaped = current_dir.replace('<', '&lt;').replace('>', '&gt;')
        html = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>File Server</title>
    <style>
        body { font-family: Arial; margin: 20px; background: #f5f5f5; }
        .header { background: #667eea; color: white; padding: 20px; border-radius: 10px; margin-bottom: 20px; }
        .file-list { background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .item { padding: 15px; border-bottom: 1px solid #eee; cursor: pointer; }
        .item:hover { background: #f0f0f0; }
        .item:last-child { border-bottom: none; }
        .icon { margin-right: 10px; font-size: 20px; }
    </style>
</head>
<body>
    <div class="header">
        <h1>📁 File Server</h1>
        <p>Server IP: """ + get_local_ip() + """</p>
        <p>Thư mục: """ + current_dir_escaped + """</p>
    </div>
    <div class="file-list">"""
        
        if not items:
            html += "<p>Thư mục trống</p>"
        else:
            for item in items:
                icon = "📁" if item["type"] == "dir" else "📄"
                name_escaped = item["name"].replace('"', '&quot;').replace("'", "&#39;")
                if item["type"] == "dir":
                    html += f'''
        <div class="item" onclick="window.location.href='/files/{name_escaped}/'">
            <span class="icon">{icon}</span>
            <strong>{name_escaped}</strong>
        </div>'''
                else:
                    html += f'''
        <div class="item" onclick="window.location.href='/files/{name_escaped}'">
            <span class="icon">{icon}</span>
            {name_escaped}
        </div>'''
        
        html += """
    </div>
</body>
</html>"""
        return html
    except Exception as e:
        import traceback
        return f"❌ Lỗi: {str(e)}<br><pre>{traceback.format_exc()}</pre>", 500
 
@app.route('/files/<path:filepath>', methods=['GET'])
def serve_file(filepath):
    """Phục vụ file từ thư mục hiện tại và các thư mục con"""
    try:
        # Loại bỏ dấu / ở cuối nếu có
        filepath = filepath.rstrip('/')
        
        # Bảo mật: chỉ cho phép truy cập trong thư mục hiện tại
        safe_path = os.path.normpath(filepath)
        if safe_path.startswith('..') or os.path.isabs(safe_path):
            return "❌ Truy cập không được phép", 403
        
        full_path = os.path.join('.', safe_path)
        
        if os.path.isdir(full_path):
            # Liệt kê file trong thư mục
            items = []
            try:
                for item in sorted(os.listdir(full_path)):
                    item_path = os.path.join(full_path, item)
                    if os.path.isdir(item_path):
                        items.append({"name": item, "type": "dir"})
                    else:
                        items.append({"name": item, "type": "file"})
            except:
                pass
            
            filepath_title = filepath.replace('<', '&lt;').replace('>', '&gt;')
            html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{filepath_title}</title>
    <style>
        body {{ font-family: Arial; margin: 20px; background: #f5f5f5; }}
        .header {{ background: #667eea; color: white; padding: 20px; border-radius: 10px; margin-bottom: 20px; }}
        .file-list {{ background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        .item {{ padding: 15px; border-bottom: 1px solid #eee; cursor: pointer; }}
        .item:hover {{ background: #f0f0f0; }}
        .item:last-child {{ border-bottom: none; }}
        .icon {{ margin-right: 10px; font-size: 20px; }}
        a {{ text-decoration: none; color: inherit; display: block; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>📁 {filepath_title}</h1>
        <a href="/" style="color: white;">← Về trang chủ</a>
    </div>
    <div class="file-list">"""
            
            for item in items:
                icon = "📁" if item["type"] == "dir" else "📄"
                name_escaped = item["name"].replace('"', '&quot;').replace("'", "&#39;")
                filepath_escaped = filepath.replace('"', '&quot;').replace("'", "&#39;")
                if item["type"] == "dir":
                    html += f'''
        <div class="item" onclick="window.location.href='/files/{filepath_escaped}/{name_escaped}/'">
            <span class="icon">{icon}</span>
            <strong>{name_escaped}</strong>
        </div>'''
                else:
                    html += f'''
        <div class="item" onclick="window.location.href='/files/{filepath_escaped}/{name_escaped}'">
            <span class="icon">{icon}</span>
            {name_escaped}
        </div>'''
            
            html += """
    </div>
</body>
</html>"""
            return html
        elif os.path.isfile(full_path):
            # Phục vụ file
            return send_file(full_path)
        else:
            return "❌ File không tồn tại", 404
    except Exception as e:
        return f"❌ Lỗi: {str(e)}", 500

@app.route('/<path:filepath>', methods=['GET'])
def catch_all(filepath):
    """Xử lý các route khác - thử phục vụ file"""
    try:
        safe_path = os.path.normpath(filepath)
        if safe_path.startswith('..') or os.path.isabs(safe_path):
            return "❌ Truy cập không được phép", 403
        
        full_path = os.path.join('.', safe_path)
        if os.path.isfile(full_path):
            return send_file(full_path)
    except:
        pass
    
    return "❌ Không tìm thấy", 404

if __name__ == "__main__":
    local_ip = get_local_ip()
    port = input(f"🚪 Nhập cổng [Mặc định: 7777]: ").strip()
    port = int(port) if port else 7777
    
    print(f"\n✅ Server tại http://{local_ip}:{port}")
    print(f"💡 Dừng: Ctrl+C\n")
    
    app.run(host="0.0.0.0", port=port)
