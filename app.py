from fastapi import FastAPI, HTTPException, Response, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime, timedelta, timezone
from supabase import create_client
from openai import OpenAI
import os

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
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ["SUPABASE_KEY"]
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
    allow_origins=[
        "https://あなたのgithubid.github.io",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------
# Schemas
# -----------------------------
class ChatIn(BaseModel):
    text: str

class ChatOut(BaseModel):
    reply: str
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
            {"role": "system", "content": "あなたは親しみやすく、感情豊かなアシスタントです。"},
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
