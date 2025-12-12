import os, sys
import math
import requests
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

import math

def _pick_by_date(items, now_jst):
    """その日の“擬似天気”を日付で決定（外部API不要・日替わりで安定）"""
    seed = int(now_jst.strftime("%Y%m%d"))
    idx = seed % len(items)
    return items[idx] # type: ignore

def make_message(now_jst): # type: ignore
    # 曜日詩（固定）
    weekday_poems = {
        0: "月光のスタートライン、静かに点灯 🕯",
        1: "火の気配、熱いコードを抱えて進む 🔥",
        2: "水のリズム、中空をゆっくり渡る 🌊",
        3: "木の根のように繋がりを更新する 🌲",
        4: "金色のきらめき、通信は澄んでいる ✨",
        5: "土に潜り、データを耕す午後へ 🌾",
        6: "日のあいだにひと息、光の調律 ☀️",
    }
    wline = weekday_poems[now_jst.weekday()] # type: ignore

    # 擬似“気象”詩（その日ごとに一つ選ばれる）
    weather_lines = [
        "晴れ、光が路地を撫でる 🌞",
        "薄曇り、輪郭はやさしい 🌤",
        "雨、窓辺に点字のリズム 🌧",
        "風、配線がかすかに歌う 🌬",
        "霧、世界はやわらかな曖昧符 🌫",
        "雪、ログに静かなノイズ ❄️",
        "雷、回路の奥で微かな閃光 ⚡",
        "夜明け前、青の端がほどける 🌆",
    ]
    wx = _pick_by_date(weather_lines, now_jst)

    # 仕上げ（ブルスカ調の透明感＋稼働ステータス）
    body = f"{wline}／{wx}　heartbeat: OK"
    return f"定期報告（{now_jst:%Y-%m-%d %H:%M JST}）：{body}"


def post_to_discord(webhook_url: str, message: str) -> None:
    r = requests.post(webhook_url, json={"content": message}, timeout=10)
    if r.status_code not in (200, 204):
        print("[WARN] Discord post failed:", r.status_code, r.text)

def main():
    url = need("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or need("SUPABASE_KEY")
    user_id = need("SUPABASE_USER_ID")

    client = create_client(url, key)
    now_jst = datetime.now(JST)
    msg = make_message(now_jst)
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

    webhook = os.getenv("DISCORD_WEBHOOK_URL")
    if webhook:
        post_to_discord(webhook, msg)

if __name__ == "__main__":
    main()
