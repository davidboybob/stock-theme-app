from __future__ import annotations

import asyncio
import httpx
from typing import Optional
from app.core.config import get_settings
from app.core.kis_auth import get_access_token
from app.models.stock import StockPrice, IndexPrice

# Rate limiter: max 5 calls/sec
_semaphore = asyncio.Semaphore(5)
_call_times: list[float] = []


class KISClient:
    def __init__(self):
        self.settings = get_settings()

    async def _get_headers(self, tr_id: str) -> dict:
        token = await get_access_token()
        return {
            "content-type": "application/json",
            "authorization": f"Bearer {token}",
            "appkey": self.settings.kis_app_key,
            "appsecret": self.settings.kis_app_secret,
            "tr_id": tr_id,
            "custtype": "P",
        }

    async def _request(self, method: str, path: str, tr_id: str, **kwargs) -> dict:
        async with _semaphore:
            headers = await self._get_headers(tr_id)
            url = f"{self.settings.kis_base_url}{path}"
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.request(method, url, headers=headers, **kwargs)
                response.raise_for_status()
                return response.json()

    async def get_stock_price(self, code: str) -> StockPrice:
        data = await self._request(
            "GET",
            "/uapi/domestic-stock/v1/quotations/inquire-price",
            tr_id="FHKST01010100",
            params={"fid_cond_mrkt_div_code": "J", "fid_input_iscd": code},
        )
        output = data.get("output", {})
        return StockPrice(
            code=code,
            name=output.get("hts_kor_isnm", ""),
            current_price=int(output.get("stck_prpr", 0)),
            change_price=int(output.get("prdy_vrss", 0)),
            change_rate=float(output.get("prdy_ctrt", 0.0)),
            volume=int(output.get("acml_vol", 0)),
            high_price=int(output.get("stck_hgpr", 0)),
            low_price=int(output.get("stck_lwpr", 0)),
            open_price=int(output.get("stck_oprc", 0)),
        )

    async def get_index_price(self, index_code: str) -> IndexPrice:
        index_names = {"0001": "KOSPI", "1001": "KOSDAQ"}
        data = await self._request(
            "GET",
            "/uapi/domestic-stock/v1/quotations/inquire-index-price",
            tr_id="FHPUP02100000",
            params={"fid_cond_mrkt_div_code": "U", "fid_input_iscd": index_code},
        )
        output = data.get("output", {})
        return IndexPrice(
            code=index_code,
            name=index_names.get(index_code, index_code),
            current_value=float(output.get("bstp_nmix_prpr", 0.0)),
            change_value=float(output.get("bstp_nmix_prdy_vrss", 0.0)),
            change_rate=float(output.get("bstp_nmix_prdy_ctrt", 0.0)),
        )


kis_client = KISClient()
