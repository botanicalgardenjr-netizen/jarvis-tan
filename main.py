import os
import sys
from datetime import datetime, timedelta, timezone
from supabase import create_client

# ===== Settings =====
JST = timezone(timedelta(hours=9))
CONV_ID = "daily-report"        # Supabase上での会話IDタグ
SENDER_TYPE = "jarvis"
PERSONA = "jarvis-core"

def get_env(name: str) -> str:
    v = os.getenv(name)
    if not v:
        print(f"[ERROR] Missing env var: {name}", file=sys.stderr)
        sys.exit(1)
    return v

def make_message(now_jst: datetime) -> str:
    # ここを自由に編集：毎日のメッセージ生成
    return f"定期報告（{now_jst:%Y-%m-%d %H:%M JST}）：Jarvisたん稼働中！🌞"

def main():
    url = get_env("SUPABASE_URL")
    # サーバー専用（RLSバイパス）：公開厳禁
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or get_env("SUPABASE_KEY")
    user_id = get_env("SUPABASE_USER_ID")  # あなたのUUID

    client = create_client(url, key)

    now_jst = datetime.now(JST)
    message = make_message(now_jst)

    # その日1回だけにするための一意キー（YYYYMMDDで日単位）
    report_key = now_jst.strftime("daily-%Y%m%d")

    row = {
        "user_id": user_id,
        "conversation_id": CONV_ID,
        "speaker": "bot",
        "message": message,
        "content": message,          # 旧列との互換用（片付くまで）
        "sender_type": SENDER_TYPE,
        "persona": PERSONA,
        "report_key": report_key,    # ← ユニークキー
    }

    print(f"[INFO] Upserting daily report ({report_key}) ...")
    res = client.table("memory_log").upsert(row, on_conflict="report_key").execute()
    # res.data は upsertされた行（既存なら更新、なければ作成）
    print("[OK] Supabase upsert done:", res.data)

if __name__ == "__main__":
    try:
        main()
        print("[DONE] Jarvis daily job finished successfully.")
    except Exception as e:
        print("[FATAL] Job failed:", repr(e), file=sys.stderr)
        sys.exit(2)
