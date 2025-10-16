import os
from supabase import create_client
from datetime import datetime

supabase = create_client(
    os.environ["SUPABASE_URL"],
    os.environ["SUPABASE_SERVICE_ROLE_KEY"]
)
USER_ID = os.environ["SUPABASE_USER_ID"]

def save_message():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    text = f"定期報告：{now} Jarvisたんは稼働中！🌞"
    row = {
        "user_id": USER_ID,
        "conversation_id": "daily-report",
        "speaker": "bot",
        "message": text,
        "content": text,
        "sender_type": "jarvis",
        "persona": "jarvis-core",
    }
    supabase.table("memory_log").insert(row).execute()
    print("✅ Supabaseへ送信完了:", text)

if __name__ == "__main__":
    save_message()
