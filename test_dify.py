#!/usr/bin/env python3
"""
Dify APIの直接テスト用スクリプト
"""

import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()

def test_dify_api():
    """Dify APIに直接リクエストを送信してテスト"""
    
    api_key = os.getenv('DIFY_API_KEY')
    base_url = os.getenv('DIFY_BASE_URL', 'https://api.dify.ai/v1')
    user = os.getenv('DIFY_USER', 'abc-123')
    
    print(f"=== Dify API テスト開始 ===")
    print(f"API Key: {api_key}")
    print(f"Base URL: {base_url}")
    print(f"User: {user}")
    
    # エンドポイントURL
    endpoint = f"{base_url}/chat-messages"
    
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    
    payload = {
        "inputs": {},
        "query": "こんにちは、テストメッセージです",
        "response_mode": "blocking",
        "conversation_id": "",
        "user": user
    }
    
    try:
        print(f"\nリクエスト送信先: {endpoint}")
        print(f"リクエストペイロード: {json.dumps(payload, ensure_ascii=False, indent=2)}")
        
        response = requests.post(
            endpoint,
            headers=headers,
            json=payload,
            timeout=30
        )
        
        print(f"\n=== レスポンス詳細 ===")
        print(f"ステータスコード: {response.status_code}")
        print(f"レスポンスヘッダー: {dict(response.headers)}")
        print(f"Content-Type: {response.headers.get('Content-Type', 'N/A')}")
        
        # レスポンス内容の詳細
        print(f"\nレスポンステキスト (最初の500文字):")
        print(response.text[:500])
        
        if response.status_code == 200:
            try:
                response_data = response.json()
                print(f"\n✅ JSON解析成功!")
                print(f"レスポンス構造: {json.dumps(response_data, ensure_ascii=False, indent=2)}")
                
                # 応答テキストを抽出
                if 'answer' in response_data:
                    print(f"\n📝 Dify応答: {response_data['answer']}")
                else:
                    print(f"\n⚠️ 'answer'キーが見つかりません。利用可能なキー: {list(response_data.keys())}")
                
            except json.JSONDecodeError as e:
                print(f"\n❌ JSON解析エラー: {e}")
                print(f"レスポンステキスト: {response.text}")
            
        else:
            print(f"\n❌ APIエラー (ステータス: {response.status_code})")
            print(f"エラーレスポンス: {response.text}")
            
    except requests.exceptions.Timeout:
        print(f"\n❌ タイムアウトエラー (30秒)")
    except requests.exceptions.ConnectionError as e:
        print(f"\n❌ 接続エラー: {e}")
    except requests.exceptions.RequestException as e:
        print(f"\n❌ リクエストエラー: {e}")
    except Exception as e:
        print(f"\n❌ 予期しないエラー: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_dify_api()
