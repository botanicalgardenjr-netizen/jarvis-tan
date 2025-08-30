import os
import json
import requests
from openai import OpenAI
from dotenv import load_dotenv
from supabase import create_client
from uuid import uuid4

load_dotenv()

# Supabase接続
supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_ROLE_KEY")  # SERVICE_ROLEを使うならここ
)

# OpenAIクライアント初期化
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Webhook URL
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

# メモリファイル（ローカル記憶）
MEMORY_FILE = "memory.json"

# メモリ読み込み
def load_memory():
    if not os.path.exists(MEMORY_FILE):
        return {"last_user_message": "", "last_jarvis_reply": ""}
    with open(MEMORY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

# メモリ保存
def save_memory(memory):
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(memory, f, ensure_ascii=False, indent=2)

# Discordから最新のユーザー発言を取得（WebhookではなくBot方式なら応答も可能）
def fetch_user_message():
    return "今日もがんばろうね！"  # 仮メッセージ。ここをBot形式にすると双方向可能。

# ジャービス返答を生成
def generate_reply(user_message, previous_reply):
    prompt = f"""あなたは「ジャービスたん」という親しみのあるAIです。
ユーザーの最新メッセージは以下です：
「{user_message}」

あなたの前回の返答は：
「{previous_reply}」

今回の返答を短く、親しみやすく、気遣いのある口調でお願いします。"""
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "あなたは感情豊かで思いやりのあるAIです。"},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content.strip()

# Discordに送信
def send_to_discord(message):
    payload = {"content": message}
    res = requests.post(WEBHOOK_URL, json=payload)
    if res.status_code != 204:
        print("Discord送信エラー:", res.text)

# Supabaseへ保存（UUIDを自動生成）
def save_to_supabase(message):
    data = {
        "sender_type": "jarvis",
        "sender_id": str(uuid4()),
        "content": message
    }
    res = supabase.table("memory_log").insert(data).execute()
    print("Supabase:", res)

# 実行関数
def main():
    memory = load_memory()
    user_message = fetch_user_message()
    jarvis_reply = generate_reply(user_message, memory.get("last_jarvis_reply"))

    send_to_discord(jarvis_reply)
    save_to_supabase(jarvis_reply)

    memory["last_user_message"] = user_message
    memory["last_jarvis_reply"] = jarvis_reply
    save_memory(memory)

    print("🟢 ジャービスたん応答完了:", jarvis_reply)

if __name__ == "__main__":
    main()
