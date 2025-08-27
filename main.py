
import os
import json
import requests
import openai
from datetime import datetime
from time import sleep
from dotenv import load_dotenv

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
MEMORY_FILE = "memory.json"

def load_memory():
    if not os.path.exists(MEMORY_FILE):
        return {"last_message": ""}
    with open(MEMORY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_memory(memory):
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(memory, f, ensure_ascii=False, indent=2)

def generate_message(memory):
    prompt = f"""
あなたは「ジャービスたん」という親しみのあるAIで、日々生活を見守る存在です。
以下はあなたの前回の発言です：
{memory['last_message']}

今日は何を話しかけますか？短く、親しみやすい口調でお願いします。
"""
    response = openai.ChatCompletion.create(
        model="gpt-4o",
        messages=[{"role": "system", "content": "あなたは感情豊かで気遣いのできるAIです。"},
                  {"role": "user", "content": prompt}]
    )
    return response["choices"][0]["message"]["content"].strip()

def send_to_discord(message):
    payload = {"content": message}
    response = requests.post(WEBHOOK_URL, json=payload)
    if response.status_code != 204:
        print("Discord送信エラー:", response.text)

def main():
    memory = load_memory()
    new_message = generate_message(memory)
    send_to_discord(new_message)
    memory["last_message"] = new_message
    save_memory(memory)
    print("送信完了:", new_message)

if __name__ == "__main__":
    main()
