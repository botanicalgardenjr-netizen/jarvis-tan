# post.py

import os
import openai
import requests
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

openai.api_key = OPENAI_API_KEY

weekday_texts = {
    0: "月曜日だよ！今週もがんばろ〜💪",
    1: "火曜日！ちょっと慣れてきた？🐢",
    2: "水曜日のジャービスたん🌊半分だよ〜！",
    3: "木曜日！もう少しで週末🌟",
    4: "金曜日！週末直前！もうひとふんばり🔥",
    5: "土曜日〜🎉 ゆっくりできてる？",
    6: "日曜日😴 明日からの準備もぼちぼちね〜"
}

today = datetime.now().weekday()
message = weekday_texts.get(today, "やっほー！今日も元気？🌞")

payload = {
    "content": message
}

response = requests.post(WEBHOOK_URL, json=payload)

if response.status_code == 204:
    print("送信成功！")
else:
    print(f"送信失敗: {response.status_code} - {response.text}")
