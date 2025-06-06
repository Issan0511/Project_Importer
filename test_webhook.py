#!/usr/bin/env python3
"""
LINEのWebhookをテストするためのスクリプト
"""
import requests
import json

def test_line_webhook():
    """テスト用のLINE Webhookリクエストを送信"""
    
    # テスト用のLINE Webhook payload
    test_payload = {
        "destination": "xxxxxxxxxx",
        "events": [
            {
                "type": "message",
                "mode": "active",
                "timestamp": 1462629479859,
                "source": {
                    "type": "user",
                    "userId": "U206d25c2ea6bd87c17655609a1c37cb8"
                },
                "replyToken": "0f3779fba3b349968c5d07db31eab56f",
                "message": {
                    "id": "444573844083572737",
                    "type": "text",
                    "text": "災害対応の警備業務について教えて"
                }
            }
        ]
    }
    
    # ローカルサーバーのWebhook URLに送信
    webhook_url = "http://localhost:8001/linebot"
    headers = {
        "Content-Type": "application/json",
        "X-Line-Signature": "test-signature"  # テスト用の署名
    }
    
    try:
        print("=== テストWebhookリクエスト送信 ===")
        print(f"送信先: {webhook_url}")
        print(f"ペイロード: {json.dumps(test_payload, ensure_ascii=False, indent=2)}")
        
        response = requests.post(
            webhook_url,
            json=test_payload,
            headers=headers,
            timeout=30
        )
        
        print(f"レスポンスステータス: {response.status_code}")
        print(f"レスポンス内容: {response.text}")
        
        if response.status_code == 200:
            print("✅ Webhookテスト成功")
        else:
            print(f"❌ Webhookテスト失敗: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Webhookテストエラー: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_line_webhook()
