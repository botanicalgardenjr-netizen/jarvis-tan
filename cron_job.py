import os, sys
from datetime import datetime, timezone, timedelta
from supabase import create_client

JST = timezone(timedelta(hours=9))
CONV_ID = "daily-report"
SENDER_TYPE = "jarvis"
PERSONA = "jarvis-core"

def need(name: str) -> str:
    v = os.getenv(name)
    if not v:
        print(f"[FATAL] Missing env: {name}", file=sys.stderr)
        sys.exit(2)
    return v

def main():
    url = need("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or need("SUPABASE_KEY")
    user_id = need("SUPABASE_USER_ID")

    client = create_client(url, key)
    now_jst = datetime.now(JST)
    msg = f"定期報告（{now_jst:%Y-%m-%d %H:%M JST}）：Jarvisたん稼働中！🌞"
    report_key = now_jst.strftime("daily-%Y%m%d")

    row = {
        "user_id": user_id,
        "conversation_id": CONV_ID,
        "speaker": "bot",
        "message": msg,
        "content": msg,
        "sender_type": SENDER_TYPE,
        "persona": PERSONA,
        "report_key": report_key,
    }

    print(f"[INFO] Upserting daily report ({report_key}) ...")
    res = client.table("memory_log").upsert(row, on_conflict="report_key").execute()  # type: ignore
    print("[OK] Supabase upsert done:", res.data)
    print("[DONE] Jarvis daily job finished successfully.")

if __name__ == "__main__":
    main()
