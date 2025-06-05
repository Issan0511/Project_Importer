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
            
            # Step A: Dify へ問い合わせ & LINE へ返信
            print(f"=== Dify への問い合わせ開始 ===", flush=True)
            dify_response = await line_dify.process_request(request_body=raw_body, signature=signature)
            print(f"=== line_dify.process_request 完了 ===", flush=True)
            
            print(f"=== Dify 応答詳細 ===", flush=True)
            print(f"応答タイプ: {type(dify_response)}", flush=True)
            print(f"応答内容 (生): {repr(dify_response)}", flush=True)
            print(f"応答内容 (str): {str(dify_response)}", flush=True)
            
            # 応答がNoneまたは空の場合の詳細ログ
            if dify_response is None:
                print("⚠️ Dify応答がNoneです", flush=True)
            elif dify_response == "":
                print("⚠️ Dify応答が空文字列です", flush=True)
            elif isinstance(dify_response, str) and len(dify_response.strip()) == 0:
                print("⚠️ Dify応答が空白文字のみです", flush=True)

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
                        else:
                            print(f"❌ 必要なキーが不足しています", flush=True)
                    else:
                        print(f"❌ データが辞書型ではありません: {type(data)}", flush=True)
                        
                except json.JSONDecodeError as e:
                    print(f"❌ JSON解析エラー: {e}", flush=True)
                    print(f"解析対象文字列: {repr(dify_response[:200])}", flush=True)
                except Exception as e:
                    print(f"❌ GAS連携処理中にエラー: {e}", flush=True)
                    import traceback
                    traceback.print_exc()
            else:
                print(f"❌ Dify応答が文字列ではありません: {type(dify_response)}", flush=True)
                
            print(f"=== 処理完了 ===", flush=True)
            
        except Exception as e:
            print(f"❌ 処理中にエラーが発生しました: {e}", flush=True)
            import traceback
            traceback.print_exc()

    background_tasks.add_task(process_and_forward)
    return "ok"
