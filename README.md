# Line Dify Integration

LINEボットとDifyを連携させ、Google Apps Scriptにデータを転送するシステムです。

## 機能

- LINEボットからのメッセージをDifyで処理
- Difyからの応答をLINEに返信
- 構造化されたデータをGoogle Apps Scriptに転送

## セットアップ

1. 依存関係をインストール:
```bash
pip install -r requirements.txt
```

2. 環境変数を設定:
`.env.example`を`.env`にコピーして、必要な値を設定してください。

```bash
cp .env.example .env
```

3. アプリケーションを起動:
```bash
uvicorn run:app --host 0.0.0.0 --port 8000
```

## 環境変数

- `LINE_CHANNEL_ACCESS_TOKEN`: LINEボットのチャンネルアクセストークン
- `LINE_CHANNEL_SECRET`: LINEボットのチャンネルシークレット
- `DIFY_API_KEY`: DifyのAPIキー
- `DIFY_BASE_URL`: DifyのベースURL（デフォルト: https://api.dify.ai/v1/chat-messages）
- `DIFY_USER`: Difyのユーザー識別子
- `GAS_WEBHOOK_URL`: Google Apps ScriptのWebhook URL

## エンドポイント

- `POST /linebot`: LINEからのWebhookを受信するエンドポイント

## テスト

`test_post.py`を使用してGoogle Apps Scriptへの投稿をテストできます:

```bash
python test_post.py
```
