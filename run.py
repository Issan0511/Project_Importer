from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, BackgroundTasks
from linedify import LineDify
import requests
import json
import os
from dotenv import load_dotenv

# 環境変数を読み込む
load_dotenv()

# デバッグ用: 環境変数の確認
print(f"DIFY_API_KEY: {os.getenv('DIFY_API_KEY')}")
print(f"DIFY_BASE_URL: {os.getenv('DIFY_BASE_URL')}")
print(f"DIFY_USER: {os.getenv('DIFY_USER')}")

# ① LineDify インスタンスを初期化
line_dify = LineDify(
    line_channel_access_token=os.getenv("LINE_CHANNEL_ACCESS_TOKEN"),
    line_channel_secret=os.getenv("LINE_CHANNEL_SECRET"),
    dify_api_key=os.getenv("DIFY_API_KEY"),
    dify_base_url=os.getenv("DIFY_BASE_URL", "https://api.dify.ai/v1"),
    dify_user=os.getenv("DIFY_USER", "abc-123")
)

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
    await line_dify.shutdown()

app = FastAPI(lifespan=lifespan)

# LINEメッセージ送信用のヘルパー関数
async def send_line_message(message: str, user_id: str = None):
    """LINEにメッセージを送信する"""
    try:
        if hasattr(line_dify, 'line_api') and user_id:
            # push messageを使用してメッセージを送信
            from linebot.v3.messaging import TextMessage, PushMessageRequest
            push_message_request = PushMessageRequest(
                to=user_id,
                messages=[TextMessage(text=message)]
            )
            await line_dify.line_api.push_message(push_message_request)
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
            
            # Step A: Dify へ問い合わせ & LINE へ返信
            print(f"=== Dify への問い合わせ開始 ===", flush=True)
            
            # LineDifyライブラリ経由での処理
            dify_response = await line_dify.process_request(request_body=raw_body, signature=signature)
            print(f"=== line_dify.process_request 完了 ===", flush=True)
            
            # 追加: 直接Dify APIを呼び出して生の応答も確認
            try:
                print(f"=== 直接Dify API呼び出し開始 ===", flush=True)
                
                # LINEメッセージからテキストを抽出
                message_text = None
                try:
                    request_data = json.loads(raw_body)
                    if 'events' in request_data and len(request_data['events']) > 0:
                        event = request_data['events'][0]
                        if event.get('type') == 'message' and event.get('message', {}).get('type') == 'text':
                            message_text = event['message']['text']
                            print(f"抽出されたメッセージ: {message_text}", flush=True)
                except Exception as e:
                    print(f"メッセージ抽出エラー: {e}", flush=True)
                
                if message_text:
                    import requests
                    
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
                    print(f"直接API payload: {json.dumps(payload, ensure_ascii=False)}", flush=True)
                    
                    direct_response = requests.post(
                        endpoint,
                        headers=headers,
                        json=payload,
                        timeout=30
                    )
                    
                    print(f"直接APIステータス: {direct_response.status_code}", flush=True)
                    print(f"直接APIヘッダー: {dict(direct_response.headers)}", flush=True)
                    print(f"直接API生レスポンス: {repr(direct_response.text)}", flush=True)
                    print(f"直接API応答（表示用）: {direct_response.text}", flush=True)
                    
            except Exception as e:
                print(f"直接Dify API呼び出しエラー: {e}", flush=True)
                import traceback
                traceback.print_exc()
            
            print(f"=== Dify 応答詳細分析 ===", flush=True)
            print(f"応答タイプ: {type(dify_response)}", flush=True)
            print(f"応答がNoneか: {dify_response is None}", flush=True)
            print(f"応答の真偽値: {bool(dify_response)}", flush=True)
            
            # 生の応答を詳細にログ出力
            print(f"=== 生のDify応答（repr） ===", flush=True)
            print(repr(dify_response), flush=True)
            print(f"=== 生のDify応答（str） ===", flush=True)
            print(str(dify_response), flush=True)
            
            # 文字列の場合の詳細分析
            if isinstance(dify_response, str):
                print(f"=== 文字列応答の詳細分析 ===", flush=True)
                print(f"文字列長: {len(dify_response)}", flush=True)
                print(f"空文字列か: {dify_response == ''}", flush=True)
                print(f"strip後の長さ: {len(dify_response.strip())}", flush=True)
                print(f"最初の200文字（生）: {repr(dify_response[:200])}", flush=True)
                print(f"最初の200文字（表示用）: {dify_response[:200]}", flush=True)
                print(f"最後の200文字（生）: {repr(dify_response[-200:])}", flush=True)
                print(f"最後の200文字（表示用）: {dify_response[-200:]}", flush=True)
                
                # 改行文字の分析
                print(f"改行文字数: {dify_response.count(chr(10))}", flush=True)
                print(f"タブ文字数: {dify_response.count(chr(9))}", flush=True)
                print(f"スペース文字数: {dify_response.count(' ')}", flush=True)
                
                # 全体の内容をログに出力（大きすぎる場合は分割）
                if len(dify_response) <= 2000:
                    print(f"=== 全Dify応答内容 ===", flush=True)
                    print(dify_response, flush=True)
                else:
                    print(f"=== Dify応答内容（分割出力） ===", flush=True)
                    for i in range(0, len(dify_response), 1000):
                        chunk = dify_response[i:i+1000]
                        print(f"--- チャンク {i//1000 + 1} ---", flush=True)
                        print(chunk, flush=True)
            
            # Difyの応答をLINEにも送信（LineDifyが自動送信する以外に詳細情報として）
            if user_id and dify_response:
                if isinstance(dify_response, str) and len(dify_response.strip()) > 0:
                    await send_line_message(f"🤖 Dify詳細応答:\n{str(dify_response)[:500]}", user_id)
                elif dify_response is not None:
                    await send_line_message(f"🤖 Dify応答タイプ: {type(dify_response)}\n内容: {str(dify_response)[:500]}", user_id)
            
            # 応答がNoneまたは空の場合の詳細ログ
            if dify_response is None:
                print("⚠️ Dify応答がNoneです", flush=True)
                if user_id:
                    await send_line_message("⚠️ Difyから応答がありませんでした", user_id)
            elif dify_response == "":
                print("⚠️ Dify応答が空文字列です", flush=True)
                if user_id:
                    await send_line_message("⚠️ Difyから空の応答が返されました", user_id)
            elif isinstance(dify_response, str) and len(dify_response.strip()) == 0:
                print("⚠️ Dify応答が空白文字のみです", flush=True)
                if user_id:
                    await send_line_message("⚠️ Difyから空白のみの応答が返されました", user_id)

            # Step B: Dify から JSON で構造化出力がある場合のみ GAS へ転送
            print(f"=== JSON解析開始 ===", flush=True)
            if isinstance(dify_response, str):
                print(f"文字列応答の長さ: {len(dify_response)}", flush=True)
                print(f"文字列応答の最初の100文字: {dify_response[:100]}", flush=True)
                
                try:
                    data = json.loads(dify_response)
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
                    print(f"解析対象文字列: {repr(dify_response[:200])}", flush=True)
                    if user_id:
                        await send_line_message(f"⚠️ Dify応答のJSON解析に失敗しました。\n応答: {str(dify_response)[:200]}...", user_id)
                except Exception as e:
                    print(f"❌ GAS連携処理中にエラー: {e}", flush=True)
                    if user_id:
                        await send_line_message(f"❌ GAS連携エラー: {str(e)}", user_id)
                    import traceback
                    traceback.print_exc()
            else:
                print(f"❌ Dify応答が文字列ではありません: {type(dify_response)}", flush=True)
                if user_id:
                    await send_line_message(f"⚠️ Dify応答が予期しない形式です: {type(dify_response)}", user_id)
                
            print(f"=== 処理完了 ===", flush=True)
            
        except Exception as e:
            print(f"❌ 処理中にエラーが発生しました: {e}", flush=True)
            import traceback
            traceback.print_exc()

    background_tasks.add_task(process_and_forward)
    return "ok"
