"""
簡單的 Webhook 服務，用於獲取 Line User ID

使用方法：
1. 執行此腳本: python get_user_id.py
2. 讓使用者傳訊息給您的 Line Bot
3. 終端機會顯示 User ID

注意：需要先安裝 flask: pip install flask
"""

from flask import Flask, request, jsonify
from datetime import datetime

app = Flask(__name__)

@app.route("/webhook", methods=['POST'])
def webhook():
    """接收 Line Webhook 事件"""
    try:
        data = request.json
        
        print("\n" + "="*70)
        print(f"📨 收到 Line Webhook 事件！ ({datetime.now().strftime('%H:%M:%S')})")
        print("="*70)
        
        for event in data.get('events', []):
            event_type = event.get('type')
            
            if event_type == 'message':
                # 訊息事件
                source = event.get('source', {})
                message = event.get('message', {})
                
                user_id = source.get('userId', 'N/A')
                source_type = source.get('type', 'N/A')
                message_type = message.get('type', 'N/A')
                message_text = message.get('text', 'N/A')
                
                print(f"\n📱 訊息來源類型: {source_type}")
                print(f"👤 User ID: {user_id}")
                print(f"💬 訊息類型: {message_type}")
                print(f"📝 訊息內容: {message_text}")
                
                print("\n" + "-"*70)
                print("✅ 請複製上面的 User ID，加入到 config/subscribers.json")
                print("-"*70)
                
            elif event_type == 'follow':
                # 加入好友事件
                user_id = event.get('source', {}).get('userId', 'N/A')
                print(f"\n🎉 新使用者加入好友！")
                print(f"👤 User ID: {user_id}")
                
            elif event_type == 'unfollow':
                # 封鎖/刪除好友事件
                user_id = event.get('source', {}).get('userId', 'N/A')
                print(f"\n😢 使用者封鎖或刪除好友")
                print(f"👤 User ID: {user_id}")
        
        return jsonify({'status': 'ok'})
        
    except Exception as e:
        print(f"\n❌ 處理 Webhook 時發生錯誤: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route("/", methods=['GET'])
def index():
    """首頁，顯示說明"""
    return """
    <html>
    <head><title>Line User ID Webhook</title></head>
    <body style="font-family: Arial, sans-serif; padding: 50px;">
        <h1>✅ Webhook 服務運行中</h1>
        <p>讓使用者傳訊息給您的 Line Bot，終端機會顯示 User ID。</p>
        <hr>
        <h3>設定步驟：</h3>
        <ol>
            <li>確保此服務正在運行</li>
            <li>使用 ngrok 建立外網連線：<code>ngrok http 5000</code></li>
            <li>在 Line Developers Console 設定 Webhook URL</li>
            <li>讓使用者加入好友並傳送訊息</li>
            <li>在終端機查看 User ID</li>
        </ol>
    </body>
    </html>
    """

if __name__ == '__main__':
    print("\n" + "="*70)
    print("🚀 Line User ID Webhook 服務啟動中...")
    print("="*70)
    print("\n📋 說明：")
    print("  1. 確保在 Line Developers Console 設定了 Webhook URL")
    print("  2. 如果是本地測試，使用 ngrok: ngrok http 5000")
    print("  3. 讓使用者傳訊息給您的 Line Bot")
    print("  4. User ID 會顯示在下方\n")
    print("="*70)
    print("⏳ 等待 Webhook 事件...")
    print("="*70 + "\n")
    
    # 啟動 Flask 服務
    app.run(host='0.0.0.0', port=5000, debug=True)
