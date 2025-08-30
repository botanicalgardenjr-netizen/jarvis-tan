import openai
from datetime import timezone
def generate_jarvis_reply(user_message: str) -> str:
    system_prompt = "あなたは日々の生活に寄り添う、頼れるAIアシスタント『ジャービスたん』です。"
    try:
        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            max_tokens=300
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"OpenAI返答生成エラー: {e}")
        return "（AI返答生成に失敗しました）"

# --- 構造整理・エラーハンドリング・環境変数チェック追加版 ---
import os
import openai
import requests
from dotenv import load_dotenv
from datetime import datetime
from supabase import create_client, Client

def load_env_vars():
    load_dotenv()
    required_vars = [
        "OPENAI_API_KEY", "DISCORD_WEBHOOK_URL", "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"
    ]
    env = {}
    missing = []
    for var in required_vars:
        value = os.getenv(var)
        if not value:
            missing.append(var)
        env[var] = value
    if missing:
        raise EnvironmentError(f"環境変数が未設定: {', '.join(missing)}")
    return env

def get_today_message():
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
    return weekday_texts.get(today, "やっほー！今日も元気？🌞")

def post_to_discord(webhook_url, message):
    payload = {"content": message}
    try:
        response = requests.post(webhook_url, json=payload)
        if response.status_code == 204:
            print("送信成功！")
        else:
            print(f"送信失敗: {response.status_code} - {response.text}")
        return response
    except Exception as e:
        print(f"Discord送信エラー: {e}")
        return None

def insert_to_supabase(supabase: Client, user_message):
    data = {
        "sender_type": "user",
        "sender_id": "00000000-0000-0000-0000-000000000000",  # 仮のUUID（全ゼロ）
        "persona": "user-human",
        "content": [user_message]
        # timestampカラムはテーブルに存在しないため送信しない
    }
    try:
        res = supabase.table("memory_log").insert(data).execute()
        print("Supabase送信成功！")
        return res
    except Exception as e:
        print(f"Supabase送信エラー: {e}")
        return None

def main():

    try:
        env = load_env_vars()
    except EnvironmentError as e:
        print(e)
        return

    openai.api_key = env["OPENAI_API_KEY"]
    user_message = get_today_message()

    # ユーザー発言をSupabaseに保存
    supabase = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    insert_to_supabase(supabase, user_message)

    # AI返答生成
    jarvis_reply = generate_jarvis_reply(user_message)

    # Jarvis返答をSupabaseに保存（timestampカラムは送信しない）
    try:
        data = {
            "sender_type": "jarvis",
            "sender_id": "00000000-0000-0000-0000-000000000000",
            "persona": "ai-jarvis",
            "content": [jarvis_reply]
        }
        supabase.table("memory_log").insert(data).execute()
        print("Jarvis返答をSupabaseに保存しました")
    except Exception as e:
        print(f"Supabase(Jarvis返答)送信エラー: {e}")

    # Discordに送信
    post_to_discord(env["DISCORD_WEBHOOK_URL"], jarvis_reply)

if __name__ == "__main__":
    main()

# --- ここまで改良版 ---

# 【主な変更点】
# ・関数化で構造整理
# ・環境変数未設定時は明示的にエラー表示して停止
# ・API通信/Supabase送信時にtry-exceptでエラーハンドリング
# ・未定義変数（message→user_message）修正
# ・main()で全体の流れを管理
# ・print出力を統一