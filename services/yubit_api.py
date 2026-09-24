import asyncio
import hashlib
import hmac
import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import quote, urlencode

import aiohttp
from yarl import URL

from config import (
    UID_MAX_LENGTH,
    UID_MIN_LENGTH,
    YUBIT_API_KEY,
    YUBIT_BASE_URL,
    YUBIT_RECV_WINDOW,
    YUBIT_SECRET_KEY,
    logger,
)


def validate_uid(uid: str) -> bool:
    return bool(
        uid
        and uid.isdigit()
        and UID_MIN_LENGTH <= len(uid) <= UID_MAX_LENGTH
    )


def encode_json_body(payload: Dict[str, Any]) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def encode_query(params: Dict[str, Any]) -> str:
    """Match Yubit's examples: spaces as %20, time colons unchanged."""
    return urlencode(params, quote_via=quote, safe=":")


def _is_success(code: Any) -> bool:
    return str(code) == "0"


def _format_api_time(timestamp_ms: int) -> str:
    return datetime.fromtimestamp(
        timestamp_ms / 1000,
        tz=timezone.utc,
    ).strftime("%Y-%m-%d %H:%M:%S")


class YubitAPI:
    """Authenticated client for Yubit Partner OpenAPI v1."""

    def __init__(self) -> None:
        self.api_key = YUBIT_API_KEY
        self.secret_key = YUBIT_SECRET_KEY
        self.base_url = YUBIT_BASE_URL
        self.recv_window = YUBIT_RECV_WINDOW
        self._session: Optional[aiohttp.ClientSession] = None
        self._timeout = aiohttp.ClientTimeout(total=20)
        self._rate_lock = asyncio.Lock()
        self._last_request_at = 0.0

    async def get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self._timeout)
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    def _generate_signature(
        self,
        method: str,
        path: str,
        timestamp: str,
        payload: str,
    ) -> str:
        source = (
            f"{method.upper()}{path}{timestamp}{self.api_key}"
            f"{self.recv_window}{payload}"
        )
        return hmac.new(
            self.secret_key.encode("utf-8"),
            source.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    async def _respect_rate_limit(self) -> None:
        # The documented private GET limit is 5 requests/second.
        async with self._rate_lock:
            elapsed = time.monotonic() - self._last_request_at
            if elapsed < 0.21:
                await asyncio.sleep(0.21 - elapsed)
            self._last_request_at = time.monotonic()

    async def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        body: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        method = method.upper()
        query = encode_query(params or {})
        payload = query if method == "GET" else encode_json_body(body or {})
        timestamp = str(int(time.time() * 1000))
        signature = self._generate_signature(
            method,
            path,
            timestamp,
            payload,
        )
        headers = {
            "Content-Type": "application/json",
            "MF-ACCESS-API-KEY": self.api_key,
            "MF-ACCESS-SIGN": signature,
            "MF-ACCESS-TIMESTAMP": timestamp,
            "MF-ACCESS-RECV-WINDOW": str(self.recv_window),
            "MF-ACCESS-SIGN-VERSION": "2",
        }
        url = self.base_url + path
        if query:
            url += "?" + query

        await self._respect_rate_limit()
        session = await self.get_session()
        try:
            async with session.request(
                method,
                URL(url, encoded=True),
                data=payload.encode("utf-8") if method == "POST" else None,
                headers=headers,
            ) as response:
                text = await response.text()
                if response.status != 200:
                    logger.error(
                        "Yubit API HTTP error: status=%s body=%s",
                        response.status,
                        text[:300],
                    )
                    raise RuntimeError(
                        f"Yubit HTTP error: {response.status}"
                    )
                try:
                    data = json.loads(text)
                except json.JSONDecodeError as exc:
                    raise RuntimeError(
                        "Yubit returned invalid JSON."
                    ) from exc
                if not isinstance(data, dict):
                    raise RuntimeError("Unexpected Yubit response.")
                return data
        except aiohttp.ClientError:
            logger.exception("Yubit network error")
            raise

    async def _fetch_balance(self, uid: str) -> Dict[str, Any]:
        try:
            data = await self._request(
                "GET",
                "/oapi/partner/affiliate/private/v1/get-user-all-balance",
                params={"uid": str(uid)},
            )
        except Exception:
            logger.exception("Yubit balance request failed for uid=%s", uid)
            return {"status": "error", "balance": None}

        code = data.get("code")
        if str(code) == "42000012" or data.get("result") is False:
            return {"status": "not_found", "balance": None}
        if not _is_success(code):
            logger.warning(
                "Yubit balance error for uid=%s: code=%s message=%s",
                uid,
                code,
                data.get("msg") or data.get("message"),
            )
            return {"status": "error", "balance": None}

        result = data.get("result")
        if not isinstance(result, dict):
            return {"status": "not_found", "balance": None}
        items = result.get("items") or []
        if not isinstance(items, list) or not items:
            return {"status": "not_found", "balance": None}

        matching = next(
            (
                item
                for item in items
                if isinstance(item, dict)
                and str(item.get("uid")) == str(uid)
            ),
            items[0],
        )
        try:
            return {
                "status": "ok",
                "balance": float(matching["totalBalance"]),
            }
        except (KeyError, TypeError, ValueError):
            logger.exception("Unexpected Yubit balance payload for uid=%s", uid)
            return {"status": "error", "balance": None}

    async def get_balance(self, uid: str) -> Optional[float]:
        result = await self._fetch_balance(uid)
        if result["status"] != "ok":
            return None
        return result["balance"]

    async def validate_user(self, uid: str) -> Dict[str, Any]:
        # The balance endpoint also verifies direct-subordinate ownership and
        # avoids validateUser's contradictory uid/email requirement.
        result = await self._fetch_balance(uid)
        if result["status"] == "not_found":
            return {
                "success": False,
                "message": "Direct referral not found",
            }
        if result["status"] != "ok":
            return {
                "success": False,
                "message": "Balance error",
            }
        return {
            "success": True,
            "balance": result["balance"],
        }

    async def _get_paged_rows(
        self,
        path: str,
        params: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        page_num = 1
        page_size = 100

        while True:
            page_params = {
                **params,
                "page_num": page_num,
                "page_size": page_size,
            }
            data = await self._request("GET", path, params=page_params)
            if not _is_success(data.get("code")):
                raise RuntimeError(
                    "Yubit API failed: "
                    f"code={data.get('code')} "
                    f"message={data.get('message') or data.get('msg')}"
                )
            page = data.get("data") or {}
            if not isinstance(page, dict):
                raise RuntimeError("Unexpected Yubit paging response.")
            page_rows = page.get("list") or []
            if not isinstance(page_rows, list):
                raise RuntimeError("Unexpected Yubit row list.")
            rows.extend(
                row for row in page_rows if isinstance(row, dict)
            )

            total = int(page.get("total_count") or len(rows))
            if not page_rows or len(rows) >= total:
                break
            page_num += 1

        return rows

    async def get_trading_volume(
        self,
        uid: Optional[str],
        market_type: str,
        start_time: int,
        end_time: int,
    ) -> List[Dict[str, Any]]:
        trade_type = {
            "spot": "spot",
            "swap": "futures",
            "futures": "futures",
        }.get(market_type)
        if trade_type is None:
            raise ValueError("market_type must be spot or futures.")

        params: Dict[str, Any] = {
            "start_time": _format_api_time(start_time),
            "end_time": _format_api_time(end_time),
            "trade_type": trade_type,
        }
        if uid:
            params["uid"] = str(uid)

        rows = await self._get_paged_rows(
            "/oapi/partner/affiliate/private/v1/transAmountList",
            params,
        )
        normalized: List[Dict[str, Any]] = []
        for row in rows:
            symbol = (
                row.get("symbol")
                or row.get("transCoinPair")
                or row.get("coinPair")
                or row.get("tradeType")
                or trade_type.upper()
            )
            amount = (
                row.get("totalAmount")
                or row.get("transAmount")
                or row.get("tradeAmount")
                or row.get("amount")
                or 0
            )
            normalized.append(
                {
                    **row,
                    "symbol": str(symbol),
                    "totalAmount": amount,
                }
            )
        return normalized

    async def get_commission_report(
        self,
        uid: Optional[str],
        start_time: int,
        end_time: int,
    ) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {
            "start_time": _format_api_time(start_time),
            "end_time": _format_api_time(end_time),
        }
        if uid:
            params["uid"] = str(uid)

        data = await self._request(
            "GET",
            "/oapi/partner/affiliate/private/v1/totalCommission",
            params=params,
        )
        if not _is_success(data.get("code")):
            raise RuntimeError(
                f"Yubit commission API failed: code={data.get('code')}"
            )
        result = data.get("data") or {}
        if not isinstance(result, dict):
            raise RuntimeError("Unexpected Yubit commission response.")
        return [
            {
                "commissionAmount": result.get("totalCommission") or 0,
            }
        ]


yubit = YubitAPI()
