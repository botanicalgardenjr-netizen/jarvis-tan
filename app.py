from fastapi import FastAPI, HTTPException # type: ignore
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware # type: ignore
import os
from datetime import datetime, timedelta, timezone
from supabase import create_client
from openai import OpenAI
from fastapi import Response # type: ignore
from fastapi.middleware.cors import CORSMiddleware # type: ignore
from pydantic import BaseModel
import traceback, logging # type: ignore
from fastapi import HTTPException, Response, Request # type: ignore

JST = timezone(timedelta(hours=9))
CONV_ID = "live-chat"
SENDER_TYPE = "jarvis"
PERSONA = "jarvis-core"

# --- env ---
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ["SUPABASE_KEY"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
USER_ID = os.environ["SUPABASE_USER_ID"]  # とりあえずあなた固定。将来はJWTから取得に。

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
oai = OpenAI(api_key=OPENAI_API_KEY)

# --- app ---
app = FastAPI(title="Jarvis Chat API") # type: ignore

# CORS（必要に応じて許可元を絞ってOK）
app.add_middleware( # type: ignore
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

class ChatIn(BaseModel):
    text: str

class ChatOut(BaseModel):
    reply: str
    jst_time: str

def log_row(speaker: str, text: str):
    supabase.table("memory_log").insert({ # type: ignore
        "user_id": USER_ID,
        "conversation_id": CONV_ID,
        "speaker": speaker,
        "message": text,
        "content": text,              # 旧列互換
        "sender_type": SENDER_TYPE if speaker=="bot" else "user",
        "persona": PERSONA if speaker=="bot" else "tori",
    }).execute()

@app.post("/chat", response_model=ChatOut) # type: ignore
def chat(payload: ChatIn):
    user_text = payload.text.strip()
    if not user_text:
        raise HTTPException(400, "text is empty")

    # 1) ユーザー発言を保存
    log_row("user", user_text)

    # 2) 返事を生成
    completion = oai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role":"system","content":"あなたは親しみやすく、簡潔で、相手の気持ちを汲むアシスタントです。"},
            {"role":"user","content": user_text}
        ],
        temperature=0.6,
    )
    reply = completion.choices[0].message.content.strip() # type: ignore

    # 3) 返答を保存
    log_row("bot", reply)

    now = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S JST")
    return ChatOut(reply=reply, jst_time=now)

@app.get("/health", include_in_schema=False) # type: ignore
def health_get():
    return {"ok": True}

@app.head("/health", include_in_schema=False) # type: ignore
def health_head(): # type: ignore
    return Response(status_code=200) # type: ignore

@app.get("/", include_in_schema=False) # type: ignore
def root(): # type: ignore
    return {"service": "jarvis-chat", "ok": True} # type: ignore

APP_VERSION = "2025.10.16-a"
@app.get("/version", include_in_schema=False) # type: ignore
def version():
    return {"version": APP_VERSION}

app.add_middleware( # type: ignore
    CORSMiddleware,
    allow_origins=["https://botanicalgardenjr-netizen.github.io"],
    allow_methods=["POST","GET","OPTIONS"],
    allow_headers=["Content-Type","Authorization"],
)

logger = logging.getLogger("app")

@app.post("/chat") # type: ignore
def chat(req: RequestModel): # type: ignore
    try:
        ...
    except Exception:
        logger.exception("chat failed")
        raise HTTPException(status_code=500, detail="internal_error")

