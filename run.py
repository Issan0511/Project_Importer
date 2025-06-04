from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, BackgroundTasks
from linedify import LineDify
import requests
import json

# ① LineDify インスタンスを初期化
line_dify = LineDify(
    line_channel_access_token="znnvM7aQHXQRVqejCRWWOl0gU2AVmSMFumHimdGWr4U4Ld+ofzw/+lNJS7iHjqsC7TfrBBcndkN3n9+KPTzLpj55Z0nXZP2FO2kKWEjXscl1SL6DLiRBgiozbVrzbDwd145mxYl6ywrcEttznq2ZwgdB04t89/1O/w1cDnyilFU=",
    line_channel_secret="6eb7d33e1e00e1c83a95c9033b96f514",
    dify_api_key="app-6AmfqBtiwIysD2kjRwVY2hhD",
    dify_base_url="https://api.dify.ai/v1/chat-messages",
    dify_user="abc-123"
)

# ② GAS へ POST するユーティリティ関数
def post_to_gas(payload: dict):
    """指定の payload(JSON) を GAS WebApp に POST してレスポンスを文字列で返す"""
    url = (
        "https://script.google.com/macros/s/"
        "AKfycbyEHqJCrHfjlseaeLmfl09WVtwWn2rboihb7l0CpIRar_YnrS9eLBeDMjaTc1OyxWqW/exec"
    )

    headers = {"Content-Type": "application/json; charset=utf-8"}
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=10)
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
    def process_and_forward():
        # Step A: Dify へ問い合わせ & LINE へ返信
        dify_response = line_dify.process_request(request_body=raw_body, signature=signature)

        # Step B: Dify から JSON で構造化出力がある場合のみ GAS へ転送
        try:
            data = json.loads(dify_response) if isinstance(dify_response, str) else dify_response
            required_keys = {"overview", "location", "startDate", "vehicle", "headCount", "operation", "hours", "amount", "cases", "training"}
            if required_keys.issubset(data.keys()):
                gas_result = post_to_gas(data)
                # オプション: GAS の結果を LINE へも送る
                line_dify.push_message(f"GAS に書き込みました:\n{gas_result}")
        except Exception as e:
            line_dify.push_message(f"GAS 連携エラー: {e}")

    background_tasks.add_task(process_and_forward)
    return "ok"
