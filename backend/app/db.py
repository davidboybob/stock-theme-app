from __future__ import annotations

import os
from supabase import create_client, Client

_client: Client | None = None


def get_supabase() -> Client:
    global _client
    if _client is None:
        url = os.environ["SUPABASE_URL"]
        key = os.environ["SUPABASE_KEY"]
        _client = create_client(url, key)
    return _client


async def init_db() -> None:
    """Supabase는 대시보드에서 테이블을 미리 생성하므로 연결 확인만 수행"""
    try:
        client = get_supabase()
        client.table("alerts").select("id").limit(1).execute()
    except Exception as e:
        # 테이블이 없으면 경고만 출력 (서버는 기동)
        import warnings
        warnings.warn(f"Supabase 연결 확인 실패: {e}")
