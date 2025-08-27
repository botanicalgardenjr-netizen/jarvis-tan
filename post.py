import os
import requests
from dotenv import load_dotenv

load_dotenv()

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

# 曜日によってメッセージ切り替え（任意）
from datetime import datetime
def generate_message():
    weekday = datetime.now().weekday()
    messages = [
        "月曜日！今週もがんばろう💪",
        "火曜日だよ。昨日どうだった？🌱",
        "水曜日！折り返し地点だね✨",
        "木曜日〜あと少し！🍵",
        "金曜日！お疲れさま〜🎉",
        "土曜日！何して過ごす？🏖️",
        "日曜日…ゆっくり休もうね🛌"
    ]
    return messages[weekday]

data = {
    "content": generate_message()
}

response = requests.post(DISCORD_WEBHOOK_URL, json=data)

print("送信完了" if response.status_code == 204 else f"失敗: {response.status_code}")
