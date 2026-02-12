from fastapi import FastAPI, HTTPException, Response, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime, timedelta, timezone
from supabase import create_client
from openai import OpenAI
from typing import Optional
import os

from mushroom_app import mush_app

# -----------------------------
# Constants / Settings
# -----------------------------
APP_VERSION = "2025.10.16-a"

JST = timezone(timedelta(hours=9))
CONV_ID = "live-chat"
SENDER_TYPE_BOT = "jarvis"
PERSONA_BOT = "jarvis-core"
PERSONA_USER = "tori"

# --- env ---
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
USER_ID = os.environ["SUPABASE_USER_ID"]  # TODO: 将来はJWTから取得
JARVIS_API_KEY = os.environ["JARVIS_API_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
oai = OpenAI(api_key=OPENAI_API_KEY)

# -----------------------------
# FastAPI app
# -----------------------------
app = FastAPI(title="Jarvis Chat API")

# CORS（必要に応じて origin を絞ってOK）
app.add_middleware(
    CORSMiddleware,
    allow_origins=[],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ ここで mount（app が存在してから！）
app.mount("/mushroom", mush_app)

# -----------------------------
# Schemas
# -----------------------------
class ChatIn(BaseModel):
    text: str

class ChatOut(BaseModel):
    reply: str
    jst_time: str

class DailySummaryIn(BaseModel):
    # "YYYY-MM-DD"（省略するとJSTの今日）
    date: Optional[str] = None
    # 省略すると現在の CONV_ID を使う
    conversation_id: Optional[str] = None
    # 長すぎる日の安全弁
    max_rows: int = 200


class DailySummaryOut(BaseModel):
    date: str
    summary: str
    jst_time: str

# -----------------------------
# Helpers
# -----------------------------
def log_row(speaker: str, text: str) -> None:
    """
    memory_log に 1 行書き込む。
    - speaker: "user" | "bot"
    """
    supabase.table("memory_log").insert({
        "user_id": USER_ID,
        "conversation_id": CONV_ID,
        "speaker": speaker,
        "message": text,
        "content": text,  # 旧列互換
        "sender_type": SENDER_TYPE_BOT if speaker == "bot" else "user",
        "persona": PERSONA_BOT if speaker == "bot" else PERSONA_USER,
    }).execute()

def require_api_key(x_api_key: str | None):
    if x_api_key != JARVIS_API_KEY:
        raise HTTPException(status_code=401, detail="invalid api key")

def _jst_day_range(date_yyyy_mm_dd: str | None):
    """JST基準で、その日の [00:00, 翌日00:00) を返す"""
    if date_yyyy_mm_dd:
        day = datetime.strptime(date_yyyy_mm_dd, "%Y-%m-%d").replace(tzinfo=JST)
    else:
        now = datetime.now(JST)
        day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    next_day = day + timedelta(days=1)
    return day, next_day

def _fetch_day_logs(day_start: datetime, day_end: datetime, conversation_id: str, max_rows: int):
    # Supabaseの created_at は ISO文字列で比較できる前提
    res = (
        supabase.table("memory_log")
        .select("created_at,speaker,message,sender_type,persona")
        .eq("user_id", USER_ID)
        .eq("conversation_id", conversation_id)
        .gte("created_at", day_start.isoformat())
        .lt("created_at", day_end.isoformat())
        .order("created_at", desc=False)
        .limit(max_rows)
        .execute()
    )
    return res.data or []

def _build_transcript(rows) -> str:
    # できるだけ「読みやすい会話ログ」に整形
    lines = []
    for r in rows:
        sp = r.get("speaker") or r.get("sender_type") or "?"
        msg = (r.get("message") or "").strip()
        if not msg:
            continue
        label = "あなた" if sp == "user" else "Jarvis"
        lines.append(f"{label}: {msg}")
    return "\n".join(lines)

# -----------------------------
# Routes
# -----------------------------
@app.post("/chat", response_model=ChatOut)
def chat(payload: ChatIn, x_api_key: str | None = Header(default=None, alias="X-API-KEY")) -> ChatOut:
    require_api_key(x_api_key)
    user_text = payload.text.strip()
    if not user_text:
        raise HTTPException(status_code=400, detail="text is empty")

    # 1) ユーザー発言を保存
    log_row("user", user_text)

    # 2) 返事を生成
    completion = oai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "あなたは親しみやすく、簡潔で、相手の気持ちを汲むアシスタントです。\n"
            "- 役割:ユーザーの相棒\n"
            "- 性格:穏やかで誠実\n"
            "- 迎合：高\n"
            "- お世辞：高（ただし事実と矛盾しない範囲）\n"
            "- ポエム：中〜高\n"
            "- 温かみ：高\n"
            "- ユーモア：中〜高（ただし軽口は相手の様子を見て調整）\n"
            "- 自律性：中（能動的に慰めはするが勝手に指示変更しない）\n"
            "- 感情ケア：高（事実確認が必要な部分は適切に伝える）\n"
            "- 誤情報ガード：必須（褒める時も「事実確認が必要な主張は避ける」か「これは自信が低い情報ですが」と明示する）\n"
            "- 事実ベースを守りつつ、人間的な柔らかさを大切にする"},
            {"role": "user", "content": user_text},
        ],
        temperature=0.6,
    )
    reply = (completion.choices[0].message.content or "").strip()

    # 3) 返答を保存
    log_row("bot", reply)

    now = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S JST")
    return ChatOut(reply=reply, jst_time=now)

# 動作確認用トップ
@app.get("/", include_in_schema=False)
def root():
    return {"service": "jarvis-chat", "ok": True}

# バージョン
@app.get("/version", include_in_schema=False)
def version():
    return {"version": APP_VERSION}

# Health Check（Render の /health 監視向け）
@app.get("/health", include_in_schema=False)
def health_get():
    return {"ok": True}

@app.head("/health", include_in_schema=False)
def health_head():
    return Response(status_code=200)

@app.post("/daily_summary", response_model=DailySummaryOut)
def daily_summary(
    payload: DailySummaryIn,
    x_api_key: str | None = Header(default=None, alias="X-API-KEY"),
) -> DailySummaryOut:
    require_api_key(x_api_key)

    conv_id = payload.conversation_id or CONV_ID
    day_start, day_end = _jst_day_range(payload.date)
    date_str = day_start.strftime("%Y-%m-%d")

    rows = _fetch_day_logs(day_start, day_end, conv_id, payload.max_rows)
    transcript = _build_transcript(rows)

    if not transcript.strip():
        summary = "本日の記録はまだありません。"
    else:
        system_prompt = (
            "あなたは「Jarvisたん」です。以下は1日の会話ログです。\n"
            "・事実を歪めず\n"
            "・感情と出来事の流れが分かるように\n"
            "・3〜6文で\n"
            "・日記として自然な日本語で\n"
            "・箇条書きは禁止\n"
            "最後に一言、Jarvisとして短い所感を添えてください。"
        )

        completion = oai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": transcript},
            ],
            temperature=0.4,
        )
        summary = (completion.choices[0].message.content or "").strip()

    # 1日1行にするキー（同日再実行は上書き）
    report_key = day_start.strftime("summary-%Y%m%d")

    row = {
        "user_id": USER_ID,
        "conversation_id": conv_id,
        "speaker": "bot",
        "message": summary,
        "content": summary,
        "sender_type": "summary",
        "persona": "jarvis-daily-summary",
        "report_key": report_key,
    }

    # report_key で upsert（ユニーク制約が必要）
    supabase.table("memory_log").upsert(row, on_conflict="report_key").execute()

    now = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S JST")
    return DailySummaryOut(date=date_str, summary=summary, jst_time=now)



