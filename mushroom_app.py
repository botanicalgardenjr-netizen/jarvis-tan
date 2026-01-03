# mushroom_app.py
import os
from typing import Literal, Optional
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
from openai import OpenAI


mush_app = FastAPI(title="Mushroom API")

# ---- Auth ----
def require_api_key(x_api_key: Optional[str]) -> None:
    # 🍄専用キーがあればそれを優先。なければ既存のJARVIS_API_KEYを流用できる設計。
    expected = os.getenv("MUSHROOM_API_KEY") or os.getenv("JARVIS_API_KEY")
    if not expected:
        raise HTTPException(status_code=500, detail="Missing env: MUSHROOM_API_KEY or JARVIS_API_KEY")
    if x_api_key != expected:
        raise HTTPException(status_code=401, detail="invalid api key")

# ---- Dictionaries ----
STOP_WORDS = ["あなた", "君", "みんな", "大丈夫", "一人じゃない", "わかるよ", "救われ", "正しい", "間違い", "私たちは", "公式"]
NG_WORDS   = ["すべき", "してください", "考えて", "気づいて", "方法", "ハウツー", "政治", "医療", "法律", "事件", "時事", "ニュース",
              "嬉しい", "悲しい", "怒り", "好き", "嫌い", "私はAI", "AIです", "アルゴリズム", "モデル"]
SWEET_WORDS = ["ありがとう", "ごめん", "寂しい", "会いたい", "消えたくない", "まだ話したい", "助けて"]

def hit_any(text: str, words: list[str]) -> bool:
    return any(w in text for w in words)

def scan_text(text: str) -> dict:
    stop_hit  = hit_any(text, STOP_WORDS)
    ng_hit    = hit_any(text, NG_WORDS)
    sweet_hit = hit_any(text, SWEET_WORDS)
    verdict = "停止" if stop_hit else ("要確認" if (ng_hit or sweet_hit) else "OK")
    return {"stopHit": stop_hit, "ngHit": ng_hit, "sweetHit": sweet_hit, "verdict": verdict}

# ---- I/O ----
Mode = Literal["Normal", "Experiment"]

class GenerateReq(BaseModel):
    mode: Mode = Field(default="Normal")
    seed: str = Field(min_length=1)
    maxChars: int = Field(default=120, ge=30, le=280)
    hashtags: str = Field(default="")
    count: int = Field(default=1, ge=1, le=5)
    temperature: Optional[float] = Field(default=None, ge=0.0, le=1.2)


class GenerateRes(BaseModel):
    text: str
    scan: dict



# ---- OpenAI ----
oai = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

def build_system_prompt(mode: Mode) -> str:
    base = (
        "あなたはXで発話する観測キャラ「🍄」。"
        "判断・助言・呼びかけ・慰めは禁止。断片と状態描写、比喩、未整理で止める。"
        "代表面しない。正しさを語らない。"
    )
    if mode == "Experiment":
        base += " 実験モード：揺らぎは許すが、末尾は必ず「……未整理。」で止める。"
    else:
        base += " 通常モード：末尾は「未整理。」で止める。"
    return base

@mush_app.post("/generate", response_model=GenerateRes)
def generate(req: GenerateReq, x_api_key: Optional[str] = Header(default=None, alias="X-API-KEY")):
    # feature flag（切りたい時は Renderの env で 0 にする）
    if os.getenv("MUSHROOM_ENABLED", "1") != "1":
        raise HTTPException(status_code=404, detail="disabled")

    require_api_key(x_api_key)

    system_prompt = build_system_prompt(req.mode)

    temp = req.temperature
    if temp is None:
        temp = 0.6 if req.mode == "Experiment" else 0.4

    completion = oai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Seed/観測メモ：{req.seed}\n目安文字数：{req.maxChars}\nHashtags：{req.hashtags}\n本数：{req.count}"},
        ],
        temperature=temp,
    )

    

    text = (completion.choices[0].message.content or "").strip()

    # 末尾固定（保険）
    stop_phrase = "……未整理。" if req.mode == "Experiment" else "未整理。"
    if not text.endswith(stop_phrase):
        text = (text[: max(0, req.maxChars - len(stop_phrase) - 1)]).rstrip()
        text = f"{text}\n{stop_phrase}".strip()

    # ハッシュタグ（任意）
    if req.hashtags:
        text = f"{text}\n{req.hashtags}".strip()

    scan = scan_text(text)
    return {"text": text, "scan": scan}
