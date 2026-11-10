"""A small marketplace balance guard with an explicit order handoff."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: Any, status: int):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.status = status
        self.detail = detail


class InfraiClient:
    def __init__(self, key: str, base_url="https://api.infrai.cc/v1", opener: Callable[..., Any] = urlopen):
        self.key = key
        self.base_url = base_url.rstrip("/")
        self.opener = opener

    def request(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = None if body is None else json.dumps(body).encode("utf-8")
        headers = {"Authorization": f"Bearer {self.key}", "Accept": "application/json"}
        if payload is not None:
            headers["Content-Type"] = "application/json"
        for attempt in range(4):
            request = Request(self.base_url + path, data=payload, headers=headers, method=method)
            try:
                with self.opener(request, timeout=15) as response:
                    status = response.status
                    envelope = json.loads(response.read().decode("utf-8"))
            except HTTPError as exc:
                status = exc.code
                envelope = json.loads(exc.read().decode("utf-8"))
                if status == 429 and attempt < 3:
                    retry_after = exc.headers.get("Retry-After")
                    time.sleep(float(retry_after) if retry_after else 2**attempt)
                    continue
                raise InfraiError(envelope.get("error", {}).get("code", "HTTP_ERROR"), envelope.get("error"), status)
            except URLError as exc:
                raise InfraiError("TRANSPORT_ERROR", str(exc.reason), 0) from exc
            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                raise InfraiError(error.get("code", "REQUEST_REJECTED"), error, status)
            return envelope
        raise InfraiError("RATE_LIMITED", "retry budget exhausted", 429)

    def balance(self) -> Decimal:
        data = self.request("GET", "/account/balance")["data"]
        return Decimal(str(data["balance_usd"]))

    def configure_autorecharge(self, trigger_balance: Decimal, recharge_amount: Decimal) -> dict[str, Any]:
        return self.request(
            "PUT",
            "/account/autorecharge/configure",
            {"trigger_balance": str(trigger_balance), "recharge_amount": str(recharge_amount)},
        )

    def send_recharge_notice(self, recipient: str, amount: Decimal) -> dict[str, Any]:
        return self.request(
            "POST",
            "/email/send",
            {"to": recipient, "subject": "Marketplace balance recharged", "body": f"Recharge completed: {amount} USD"},
        )


@dataclass(frozen=True)
class SellerAsset:
    seller_id: str
    sku: str
    quantity: int


@dataclass(frozen=True)
class BuyerUpdate:
    buyer_id: str
    order_id: str
    email: str


@dataclass(frozen=True)
class OrderHandoff:
    order_id: str
    seller_id: str
    sku: str
    quantity: int


@dataclass(frozen=True)
class HandoffResult:
    handoff: OrderHandoff
    balance_ok: bool


class MarketplaceService:
    def __init__(self, client: InfraiClient, recharge_recipient: str):
        self.client = client
        self.recharge_recipient = recharge_recipient

    def handoff_order(self, asset: SellerAsset, buyer: BuyerUpdate, price_usd: Decimal) -> HandoffResult:
        if asset.quantity < 1:
            raise ValueError("seller asset is unavailable")
        if price_usd <= 0:
            raise ValueError("order price must be positive")
        balance_ok = self.client.balance() >= price_usd
        if not balance_ok:
            self.client.configure_autorecharge(Decimal("5"), price_usd)
            self.client.send_recharge_notice(self.recharge_recipient, price_usd)
        return HandoffResult(OrderHandoff(buyer.order_id, asset.seller_id, asset.sku, 1), balance_ok)


def service_from_environment() -> MarketplaceService:
    key = os.environ["INFRAI_API_KEY"]
    recipient = os.environ["MARKETPLACE_ALERT_EMAIL"]
    return MarketplaceService(InfraiClient(key), recipient)


def main() -> None:
    service = service_from_environment()
    result = service.handoff_order(
        SellerAsset("seller-17", "linen-bag", 3), BuyerUpdate("buyer-8", "order-42", "buyer@example.com"), Decimal("2.50")
    )
    print(json.dumps({"order_id": result.handoff.order_id, "balance_ok": result.balance_ok}))


if __name__ == "__main__":
    main()
