from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, BackgroundTasks
import requests
import json
import os
from dotenv import load_dotenv
from linebot.v3.messaging import AsyncApiClient, AsyncMessagingApi, Configuration, TextMessage, ReplyMessageRequest
from linebot.v3.webhooks import WebhookParser
from linebot.v3.exceptions import InvalidSignatureError

# 環境変数を読み込む
load_dotenv()

# デバッグ用: 環境変数の確認
print(f"DIFY_API_KEY: {os.getenv('DIFY_API_KEY')}")
print(f"DIFY_BASE_URL: {os.getenv('DIFY_BASE_URL')}")
print(f"DIFY_USER: {os.getenv('DIFY_USER')}")

# LINE API クライアントを初期化
configuration = Configuration(access_token=os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
async_api_client = AsyncApiClient(configuration)
line_bot_api = AsyncMessagingApi(async_api_client)

# ② GAS へ POST するユーティリティ関数
def post_to_gas(payload: dict):
    """指定の payload(JSON) を GAS WebApp に POST してレスポンスを文字列で返す"""
    gas_url = os.getenv("GAS_WEBHOOK_URL")
    if not gas_url:
        return "GAS_WEBHOOK_URL environment variable is not set"
    
    headers = {"Content-Type": "application/json; charset=utf-8"}
    try:
        res = requests.post(gas_url, json=payload, headers=headers, timeout=10)
        return f"GAS status={res.status_code}, body={res.text}"
    except Exception as e:
        return f"GAS request failed: {e}"

# ③ アプリのライフサイクル定義
@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await async_api_client.close()

app = FastAPI(lifespan=lifespan)

# LINEメッセージ送信用のヘルパー関数
async def send_line_message(message: str, user_id: str = None):
    """LINEにメッセージを送信する"""
    try:
        if user_id:
            # push messageを使用してメッセージを送信
            from linebot.v3.messaging import PushMessageRequest
            push_message_request = PushMessageRequest(
                to=user_id,
                messages=[TextMessage(text=message)]
            )
            await line_bot_api.push_message(push_message_request)
            print(f"✅ LINEメッセージ送信完了: {message[:50]}...", flush=True)
        else:
            print(f"⚠️ LINEメッセージ送信スキップ (user_id={user_id}): {message[:50]}...", flush=True)
    except Exception as e:
        print(f"❌ LINEメッセージ送信エラー: {e}", flush=True)

# ④ Webhook エンドポイント定義
@app.post("/linebot")
async def handle_request(request: Request, background_tasks: BackgroundTasks):
    """LINE webhook からのリクエストを受け取り、
    1) Dify へ転送 → 返答を LINE に push
    2) 返答 JSON に必要フィールドがすべて揃っていれば GAS へ転送
    """
    raw_body = (await request.body()).decode("utf-8")
    signature = request.headers.get("X-Line-Signature", "")

    # linedify の処理をバックグラウンドで実行
    async def process_and_forward():
        try:
            print(f"=== 処理開始 ===", flush=True)
            print(f"Request body 長さ: {len(raw_body)}", flush=True)
            print(f"Request body 内容: {raw_body[:200]}...", flush=True)  # 最初の200文字のみ表示
            print(f"X-Line-Signature: {signature}", flush=True)
            
            # リクエストボディからuser_idを抽出
            user_id = None
            try:
                request_data = json.loads(raw_body)
                if 'events' in request_data and len(request_data['events']) > 0:
                    event = request_data['events'][0]
                    if 'source' in event and 'userId' in event['source']:
                        user_id = event['source']['userId']
                        print(f"抽出されたuser_id: {user_id}", flush=True)
            except Exception as e:
                print(f"user_id抽出エラー: {e}", flush=True)
            
            # Step A: 直接Dify APIを呼び出してGAS転送用のデータを取得
            print(f"=== Dify への問い合わせ開始 ===", flush=True)
            
            # LINEメッセージからテキストを抽出
            message_text = None
            reply_token = None
            try:
                request_data = json.loads(raw_body)
                if 'events' in request_data and len(request_data['events']) > 0:
                    event = request_data['events'][0]
                    if event.get('type') == 'message' and event.get('message', {}).get('type') == 'text':
                        message_text = event['message']['text']
                        reply_token = event.get('replyToken')
                        print(f"抽出されたメッセージ: {message_text}", flush=True)
                        print(f"Reply Token: {reply_token}", flush=True)
            except Exception as e:
                print(f"メッセージ抽出エラー: {e}", flush=True)
            
            dify_answer = None
            if message_text:
                try:
                    print(f"=== 直接Dify API呼び出し開始 ===", flush=True)
                    
                    api_key = os.getenv('DIFY_API_KEY')
                    base_url = os.getenv('DIFY_BASE_URL', 'https://api.dify.ai/v1')
                    user = os.getenv('DIFY_USER', 'abc-123')
                    
                    endpoint = f"{base_url}/chat-messages"
                    headers = {
                        'Authorization': f'Bearer {api_key}',
                        'Content-Type': 'application/json'
                    }
                    
                    payload = {
                        "inputs": {},
                        "query": message_text,
                        "response_mode": "blocking",
                        "conversation_id": "",
                        "user": user
                    }
                    
                    print(f"直接API呼び出し先: {endpoint}", flush=True)
                    
                    direct_response = requests.post(
                        endpoint,
                        headers=headers,
                        json=payload,
                        timeout=30
                    )
                    
                    print(f"直接APIステータス: {direct_response.status_code}", flush=True)
                    
                    if direct_response.status_code == 200:
                        response_data = direct_response.json()
                        dify_answer = response_data.get('answer', '')
                        print(f"Dify応答取得成功: {dify_answer}", flush=True)
                        
                        # LINEにDifyの応答を返信
                        if reply_token and dify_answer:
                            reply_request = ReplyMessageRequest(
                                replyToken=reply_token,
                                messages=[TextMessage(text=dify_answer)]
                            )
                            await line_bot_api.reply_message(reply_request)
                            print(f"✅ LINEにDify応答を返信完了", flush=True)
                    else:
                        print(f"❌ Dify API エラー: {direct_response.status_code} - {direct_response.text}", flush=True)
                        
                except Exception as e:
                    print(f"直接Dify API呼び出しエラー: {e}", flush=True)
                    import traceback
                    traceback.print_exc()
            
            # 署名検証
            try:
                print(f"=== LINE署名検証開始 ===", flush=True)
                parser = WebhookParser(os.getenv("LINE_CHANNEL_SECRET"))
                events = parser.parse(raw_body, signature)
                print(f"✅ 署名検証成功: {len(events)}個のイベント", flush=True)
            except InvalidSignatureError:
                print(f"❌ 署名検証失敗", flush=True)
                return
            except Exception as e:
                print(f"署名検証エラー: {e}", flush=True)
            
            # Step B: Dify から JSON で構造化出力がある場合のみ GAS へ転送
            print(f"=== JSON解析開始 ===", flush=True)
            if dify_answer and isinstance(dify_answer, str):
                print(f"Dify応答の長さ: {len(dify_answer)}", flush=True)
                print(f"Dify応答の最初の100文字: {dify_answer[:100]}", flush=True)
                
                try:
                    data = json.loads(dify_answer)
                    print(f"JSON解析成功: {type(data)}", flush=True)
                    print(f"解析されたデータ: {json.dumps(data, ensure_ascii=False, indent=2)}", flush=True)
                    
                    required_keys = {"overview", "location", "startDate", "vehicle", "headCount", "operation", "hours", "amount", "cases", "training"}
                    
                    if isinstance(data, dict):
                        print(f"データのキー: {list(data.keys())}", flush=True)
                        missing_keys = required_keys - set(data.keys())
                        if missing_keys:
                            print(f"不足しているキー: {missing_keys}", flush=True)
                        else:
                            print("全ての必要なキーが揃っています", flush=True)
                        
                        if required_keys.issubset(data.keys()):
                            print(f"=== GAS転送開始 ===", flush=True)
                            gas_result = post_to_gas(data)
                            print(f"✅ GAS に書き込みました: {gas_result}", flush=True)
                            
                            # GASの結果をLINEに送信
                            if user_id:
                                await send_line_message(f"📝 GAS連携結果:\n{gas_result}", user_id)
                            else:
                                print(f"user_idが不明のため、GAS結果のLINE送信をスキップ: {gas_result}", flush=True)
                        else:
                            print(f"❌ 必要なキーが不足しています", flush=True)
                            if user_id:
                                await send_line_message(f"⚠️ 必要なキーが不足しています。\n不足キー: {missing_keys}", user_id)
                    else:
                        print(f"❌ データが辞書型ではありません: {type(data)}", flush=True)
                        
                except json.JSONDecodeError as e:
                    print(f"❌ JSON解析エラー: {e}", flush=True)
                    print(f"解析対象文字列: {repr(dify_answer[:200])}", flush=True)
                    if user_id:
                        await send_line_message(f"⚠️ Dify応答のJSON解析に失敗しました。\n応答: {str(dify_answer)[:200]}...", user_id)
                except Exception as e:
                    print(f"❌ GAS連携処理中にエラー: {e}", flush=True)
                    if user_id:
                        await send_line_message(f"❌ GAS連携エラー: {str(e)}", user_id)
                    import traceback
                    traceback.print_exc()
            else:
                print(f"❌ Dify応答が取得できませんでした", flush=True)
                if user_id:
                    await send_line_message("❌ Difyからの応答取得に失敗しました", user_id)
                
            print(f"=== 処理完了 ===", flush=True)
            
        except Exception as e:
            print(f"❌ 処理中にエラーが発生しました: {e}", flush=True)
            import traceback
            traceback.print_exc()

    background_tasks.add_task(process_and_forward)
    return "ok"
