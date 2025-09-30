"""
持久化的 Line Webhook 服務
可以一直運行在背景，自動記錄所有新加入的使用者

使用方法：
1. 執行此服務（可以設定為開機自動啟動）
2. 設定 Line Webhook URL（一次性設定）
3. 之後任何時候，同事加好友或傳訊息，User ID 都會被自動記錄

儲存位置：user_ids.json
"""

from flask import Flask, request, jsonify
from datetime import datetime
import json
import os

app = Flask(__name__)

# User ID 記錄檔案
USER_IDS_FILE = 'user_ids.json'

def load_user_ids():
    """載入已記錄的 User IDs"""
    if os.path.exists(USER_IDS_FILE):
        with open(USER_IDS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'users': []}

def save_user_id(user_id, message='', event_type='message'):
    """儲存新的 User ID"""
    data = load_user_ids()
    
    # 檢查是否已存在
    existing = next((u for u in data['users'] if u['user_id'] == user_id), None)
    
    if existing:
        # 更新最後互動時間
        existing['last_interaction'] = datetime.now().isoformat()
        existing['last_message'] = message
        print(f"🔄 更新使用者: {user_id[:20]}...")
    else:
        # 新增使用者
        data['users'].append({
            'user_id': user_id,
            'first_seen': datetime.now().isoformat(),
            'last_interaction': datetime.now().isoformat(),
            'last_message': message,
            'event_type': event_type
        })
        print(f"✨ 新使用者: {user_id}")
        print(f"   訊息: {message}")
        print(f"   時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 儲存
    with open(USER_IDS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

@app.route("/webhook", methods=['POST'])
def webhook():
    """接收 Line Webhook 事件"""
    try:
        data = request.json
        
        for event in data.get('events', []):
            event_type = event.get('type')
            user_id = event.get('source', {}).get('userId')
            
            if not user_id:
                continue
            
            if event_type == 'message':
                message_text = event.get('message', {}).get('text', '')
                print(f"\n💬 收到訊息")
                save_user_id(user_id, message_text, 'message')
                
            elif event_type == 'follow':
                print(f"\n🎉 新好友加入")
                save_user_id(user_id, '', 'follow')
                
            elif event_type == 'unfollow':
                print(f"\n😢 使用者封鎖/刪除好友: {user_id[:20]}...")
        
        return jsonify({'status': 'ok'})
        
    except Exception as e:
        print(f"\n❌ 錯誤: {e}")
        return jsonify({'status': 'error'}), 500

@app.route("/users", methods=['GET'])
def list_users():
    """列出所有記錄的 User IDs（網頁介面）"""
    data = load_user_ids()
    
    html = """
    <html>
    <head>
        <title>Line User IDs</title>
        <meta charset="utf-8">
        <style>
            body { font-family: Arial, sans-serif; padding: 20px; }
            table { border-collapse: collapse; width: 100%; }
            th, td { border: 1px solid #ddd; padding: 12px; text-align: left; }
            th { background-color: #4CAF50; color: white; }
            tr:nth-child(even) { background-color: #f2f2f2; }
            .user-id { font-family: monospace; font-size: 12px; }
            .copy-btn { cursor: pointer; padding: 5px 10px; background: #2196F3; color: white; border: none; border-radius: 3px; }
        </style>
        <script>
            function copyToClipboard(text) {
                navigator.clipboard.writeText(text);
                alert('已複製: ' + text);
            }
        </script>
    </head>
    <body>
        <h1>📋 Line User IDs 記錄</h1>
        <p>總共 {count} 個使用者</p>
        <table>
            <tr>
                <th>#</th>
                <th>User ID</th>
                <th>首次加入</th>
                <th>最後互動</th>
                <th>最後訊息</th>
                <th>操作</th>
            </tr>
            {rows}
        </table>
        <hr>
        <p>💡 提示：點擊「複製」按鈕後，將 User ID 加入 config/subscribers.json</p>
    </body>
    </html>
    """
    
    rows = ""
    for i, user in enumerate(data['users'], 1):
        rows += f"""
            <tr>
                <td>{i}</td>
                <td class="user-id">{user['user_id']}</td>
                <td>{user['first_seen'][:16]}</td>
                <td>{user['last_interaction'][:16]}</td>
                <td>{user.get('last_message', 'N/A')[:30]}...</td>
                <td><button class="copy-btn" onclick="copyToClipboard('{user['user_id']}')">複製</button></td>
            </tr>
        """
    
    html = html.format(count=len(data['users']), rows=rows)
    return html

@app.route("/", methods=['GET'])
def index():
    """首頁"""
    data = load_user_ids()
    return f"""
    <html>
    <head><title>Line User ID Service</title><meta charset="utf-8"></head>
    <body style="font-family: Arial, sans-serif; padding: 50px;">
        <h1>✅ Webhook 服務運行中</h1>
        <p>目前已記錄 <strong>{len(data['users'])}</strong> 個使用者</p>
        <hr>
        <h3>📋 功能：</h3>
        <ul>
            <li><a href="/users">查看所有 User IDs</a></li>
            <li>Webhook 端點: <code>/webhook</code></li>
        </ul>
        <hr>
        <h3>使用說明：</h3>
        <ol>
            <li>使用 ngrok 建立外網連線：<code>ngrok http 5000</code></li>
            <li>在 Line Developers Console 設定 Webhook URL</li>
            <li>讓同事加入好友或傳訊息</li>
            <li>User ID 會自動儲存到 <code>user_ids.json</code></li>
            <li>訪問 <a href="/users">/users</a> 查看所有 User IDs</li>
        </ol>
    </body>
    </html>
    """

if __name__ == '__main__':
    print("\n" + "="*70)
    print("🚀 Line User ID 持久化服務啟動")
    print("="*70)
    print(f"\n📂 User IDs 儲存位置: {USER_IDS_FILE}")
    
    data = load_user_ids()
    print(f"📊 目前已記錄: {len(data['users'])} 個使用者")
    
    print("\n💡 使用方式：")
    print("  1. 訪問 http://localhost:5000 查看狀態")
    print("  2. 訪問 http://localhost:5000/users 查看所有 User IDs")
    print("  3. 使用 ngrok 設定外網 Webhook")
    print("  4. 任何時候，使用者加好友或傳訊息，User ID 都會被記錄")
    
    print("\n" + "="*70)
    print("⏳ 服務運行中... (Ctrl+C 停止)")
    print("="*70 + "\n")
    
    app.run(host='0.0.0.0', port=5000, debug=False)
