from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, BackgroundTasks
from linedify import LineDify, DifyType
from linebot.v3.messaging import TextMessage
import os
from dotenv import load_dotenv
import httpx
import json

# 環境変数を読み込む
load_dotenv()

# ① LineDify インスタンスを初期化
line_dify = LineDify(
    line_channel_access_token=os.getenv("LINE_CHANNEL_ACCESS_TOKEN"),
    line_channel_secret=os.getenv("LINE_CHANNEL_SECRET"),
    dify_api_key=os.getenv("DIFY_API_KEY"),
    dify_base_url="https://api.dify.ai/v1",
    dify_user="abc-123",
    dify_type=DifyType.Chatbot,
    verbose=True
)

# LINEの既読APIは申請が必要なため、コメントアウト
# LINE_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
# async def mark_as_read(user_id: str):
#     url = "https://api.line.me/v2/bot/message/markAsRead"
#     headers = {
#         "Content-Type": "application/json",
#         "Authorization": f"Bearer {LINE_ACCESS_TOKEN}"
#     }
#     payload = {"chat": {"userId": user_id}}
#     async with httpx.AsyncClient() as client:
#         await client.post(url, json=payload, headers=headers)

# ② アプリのライフサイクル定義
@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await line_dify.shutdown()

app = FastAPI(lifespan=lifespan)

# ③ Webhook エンドポイント定義
@app.post("/linebot")
async def handle_request(request: Request, background_tasks: BackgroundTasks):
    # リクエストボディ読み込み
    raw_body = (await request.body()).decode("utf-8")
    print(raw_body)
    # JSON解析
    data = json.loads(raw_body)
    # 既読マークをバックグラウンドで実行（API申請が必要なため一時停止）
    # if user_id:
    #     background_tasks.add_task(mark_as_read, user_id)
    # Linedifyの処理をキック
    background_tasks.add_task(
        line_dify.process_request,
        raw_body,
        signature=request.headers.get("X-Line-Signature", "")
    )
    return "ok"
