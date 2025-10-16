import os
from supabase import create_client

supabase = create_client(os.environ["SUPABASE_URL"],
                         os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ["SUPABASE_KEY"])
USER_ID = os.environ["SUPABASE_USER_ID"]

def save_to_supabase(text, speaker="bot", conv_id="jarvis-auto"):
    row = {
        "user_id": USER_ID,
        "conversation_id": conv_id,
        "speaker": speaker,
        "message": text,
        # 旧列は片付くまでミラーしておくと安心
        "content": text,
        "sender_type": "jarvis",
        "persona": "jarvis-core",
    }
    supabase.table("memory_log").insert(row).execute()
