from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, BackgroundTasks
from linedify import LineDify, DifyType
from linebot.v3.messaging import TextMessage
import os
from dotenv import load_dotenv

# 環境変数を読み込む
load_dotenv()

# ① LineDify インスタンスを初期化
line_dify = LineDify(
    line_channel_access_token=os.getenv("LINE_CHANNEL_ACCESS_TOKEN"),
    line_channel_secret=os.getenv("LINE_CHANNEL_SECRET"),
    dify_api_key=os.getenv("DIFY_API_KEY"),
    dify_base_url=os.getenv("DIFY_BASE_URL"),
    dify_user=os.getenv("DIFY_USER"),
    dify_type=DifyType[os.getenv("DIFY_TYPE", "Chatbot")],
    verbose=True
)

# ② アプリのライフサイクル定義
@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await line_dify.shutdown()

app = FastAPI(lifespan=lifespan)

# ③ Webhook エンドポイント定義
@app.post("/linebot")
async def handle_request(request: Request, background_tasks: BackgroundTasks):
    request_body=(await request.body()).decode("utf-8")
    print(request_body)
    background_tasks.add_task(
        line_dify.process_request,
        request_body,
        signature=request.headers.get("X-Line-Signature", "")
    )
    return "ok"

