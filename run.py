from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, BackgroundTasks
from linedify import LineDify, DifyType
from linebot.v3.messaging import TextMessage
# ① LineDify インスタンスを初期化
line_dify = LineDify(
    line_channel_access_token="znnvM7aQHXQRVqejCRWWOl0gU2AVmSMFumHimdGWr4U4Ld+ofzw/+lNJS7iHjqsC7TfrBBcndkN3n9+KPTzLpj55Z0nXZP2FO2kKWEjXscl1SL6DLiRBgiozbVrzbDwd145mxYl6ywrcEttznq2ZwgdB04t89/1O/w1cDnyilFU=",
    line_channel_secret="6eb7d33e1e00e1c83a95c9033b96f514",
    dify_api_key="app-6AmfqBtiwIysD2kjRwVY2hhD",
    dify_base_url="https://api.dify.ai/v1",    # e.g. https://api.dify.ai/v1
    dify_user="abc-123",
    dify_type=DifyType.Chatbot,
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

