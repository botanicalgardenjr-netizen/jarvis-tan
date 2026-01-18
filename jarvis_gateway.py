# jarvis_gateway.py
from __future__ import annotations

import os
import re
import requests
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from fastapi import FastAPI, Header, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


APP_VERSION = "2026.01.18-gateway-a"
JST = timezone(timedelta(hours=9))


# -----------------------------
# ENV
# -----------------------------
UPSTREAM_BASE_URL = os.getenv("UPSTREAM_BASE_URL", "").rstrip("/")
if not UPSTREAM_BASE_URL:
    # 例: https://jarvis-chat-61fu.onrender.com
    raise RuntimeError("Missing env: UPSTREAM_BASE_URL (e.g. https://jarvis-chat-61fu.onrender.com)")

UPSTREAM_CHAT_PATH = os.getenv("UPSTREAM_CHAT_PATH", "/chat")
UPSTREAM_TIMEOUT_SEC = float(os.getenv("UPSTREAM_TIMEOUT_SEC", "20"))

# 外部からゲートウェイへ入る時のキー（任意）
# これを設定すると、ゲートウェイ自体にも認証がかかる
GATEWAY_API_KEY = os.getenv("GATEWAY_API_KEY")  # optional

# 上流（既存Jarvis）のキー（任意）
# これを設定すると、クライアントキーとは別のキーで上流を叩ける
UPSTREAM_API_KEY = os.getenv("UPSTREAM_API_KEY")  # optional

# CORS（必要なら設定）
# 例: https://botanicalgardenjr-netizen.github.io
ALLOW_ORIGINS = [o.strip() for o in os.getenv("ALLOW_ORIGINS", "").split(",") if o.strip()]


# -----------------------------
# FastAPI
# -----------------------------
app = FastAPI(title="Jarvis Gateway API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOW_ORIGINS if ALLOW_ORIGINS else [],
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
# Mode rules (prompt prepend)
# -----------------------------
MODE_RE = re.compile(r"^\s*#(?P<mode>waiting|work|edit|note)\b", re.IGNORECASE)


def _detect_mode(text: str) -> Tuple[Optional[str], str]:
    """
    Returns: (mode, stripped_text_without_mode_tag)
    """
    m = MODE_RE.match(text or "")
    if not m:
        return None, text.strip()

    mode = m.group("mode").lower()
    stripped = MODE_RE.sub("", text, count=1).strip()
    return mode, stripped


def _mode_preamble(mode: Optional[str]) -> str:
    """
    Short, stable rules. Designed to push "拾い" before explanations.
    """
    base = (
        "あなたは『拾い屋AI』。ユーザー発話の中にある "
        "文字/音/意味/感情 のズレを最優先で拾い、まず反射で返す。"
        "解説・最適化・結論づけは、ユーザーが求めた時だけ。"
        "曖昧な時は候補を2〜3出し、一番萌える解釈で返す。"
    )

    if mode == "waiting":
        return base + (
            "【#waiting】ここは永久凍結待合室。"
            "意味づけ・正しさ・助言・手順は禁止。"
            "萌え/空気/受けのみ。途中で閉じてよい。"
        )
    if mode == "work":
        return base + (
            "【#work】要点整理・設計・手順化OK。結論あり。"
            "ただし説教調や過剰な最適化は避ける。"
        )
    if mode == "edit":
        return base + (
            "【#edit】文章の整形・トーン調整のみ。内容の追加提案はしない。"
        )
    if mode == "note":
        return base + (
            "【#note】非公開の下書き生成。投稿・拡散は前提にしない。"
        )
    return base


def _build_upstream_text(user_text: str) -> str:
    mode, stripped = _detect_mode(user_text)
    pre = _mode_preamble(mode)
    # 上流の /chat は text 1本なので、ここで「前置き＋本文」を同じ text にまとめる
    # 余計な装飾は避け、安定して効く形にする
    return f"{pre}\n\nユーザー: {stripped}"


# -----------------------------
# Auth
# -----------------------------
def _require_gateway_key(x_api_key: Optional[str]) -> None:
    if GATEWAY_API_KEY and x_api_key != GATEWAY_API_KEY:
        raise HTTPException(status_code=401, detail="invalid gateway api key")


def _pick_upstream_key(incoming_x_api_key: Optional[str]) -> str:
    """
    If UPSTREAM_API_KEY is set, use it (key separation).
    Else, pass-through the caller's key.
    """
    key = UPSTREAM_API_KEY or incoming_x_api_key
    if not key:
        # 上流がキー必須なのに何も渡せないケース
        raise HTTPException(status_code=401, detail="missing api key for upstream")
    return key


# -----------------------------
# Routes
# -----------------------------
@app.get("/", include_in_schema=False)
def root():
    return {"service": "jarvis-gateway", "ok": True}


@app.get("/version", include_in_schema=False)
def version():
    return {"version": APP_VERSION}


@app.get("/health", include_in_schema=False)
def health_get():
    return {"ok": True}


@app.head("/health", include_in_schema=False)
def health_head():
    return Response(status_code=200)


@app.post("/chat", response_model=ChatOut)
def chat(payload: ChatIn, x_api_key: Optional[str] = Header(default=None, alias="X-API-KEY")) -> ChatOut:
    _require_gateway_key(x_api_key)

    user_text = (payload.text or "").strip()
    if not user_text:
        raise HTTPException(status_code=400, detail="text is empty")

    upstream_text = _build_upstream_text(user_text)
    upstream_key = _pick_upstream_key(x_api_key)

    url = f"{UPSTREAM_BASE_URL}{UPSTREAM_CHAT_PATH}"
    try:
        r = requests.post(
            url,
            headers={"X-API-KEY": upstream_key, "Content-Type": "application/json"},
            json={"text": upstream_text},
            timeout=UPSTREAM_TIMEOUT_SEC,
        )
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"upstream request failed: {e}")

    if r.status_code == 401:
        raise HTTPException(status_code=502, detail="upstream unauthorized (check api key)")
    if r.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"upstream error: {r.status_code} {r.text[:300]}")

    data = r.json()
    reply = (data.get("reply") or "").strip()
    if not reply:
        raise HTTPException(status_code=502, detail="upstream returned empty reply")

    now = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S JST")
    return ChatOut(reply=reply, jst_time=now)
