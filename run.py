from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, BackgroundTasks
from linedify import LineDify
import requests
import json
import os
from dotenv import load_dotenv

# 環境変数を読み込む
load_dotenv()

# ① LineDify インスタンスを初期化
line_dify = LineDify(
    line_channel_access_token=os.getenv("LINE_CHANNEL_ACCESS_TOKEN"),
    line_channel_secret=os.getenv("LINE_CHANNEL_SECRET"),
    dify_api_key=os.getenv("DIFY_API_KEY"),
    dify_base_url=os.getenv("DIFY_BASE_URL", "https://api.dify.ai/v1/chat-messages"),
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
            # Step A: Dify へ問い合わせ & LINE へ返信
            dify_response = await line_dify.process_request(request_body=raw_body, signature=signature)

            # Step B: Dify から JSON で構造化出力がある場合のみ GAS へ転送
            # dify_responseがstrの場合のみJSONパースを試行
            if isinstance(dify_response, str):
                try:
                    data = json.loads(dify_response)
                    required_keys = {"overview", "location", "startDate", "vehicle", "headCount", "operation", "hours", "amount", "cases", "training"}
                    if isinstance(data, dict) and required_keys.issubset(data.keys()):
                        gas_result = post_to_gas(data)
                        print(f"GAS に書き込みました: {gas_result}")
                except json.JSONDecodeError:
                    print("Dify response is not valid JSON")
                except Exception as e:
                    print(f"GAS連携処理中にエラー: {e}")
        except Exception as e:
            print(f"処理中にエラーが発生しました: {e}")

    background_tasks.add_task(process_and_forward)
    return "ok"
