from decimal import Decimal

from src.marketplace_service import BuyerUpdate, HandoffResult, MarketplaceService, SellerAsset


class FakeClient:
    def __init__(self, balance):
        self.current = Decimal(balance)
        self.calls = []

    def balance(self):
        self.calls.append(("balance",))
        return self.current

    def configure_autorecharge(self, trigger_balance, recharge_amount):
        self.calls.append(("configure", trigger_balance, recharge_amount))

    def send_recharge_notice(self, recipient, amount):
        self.calls.append(("email", recipient, amount))


def test_low_balance_configures_recharge_before_order_handoff():
    client = FakeClient("1.00")
    service = MarketplaceService(client, "ops@example.com")

    result = service.handoff_order(
        SellerAsset("seller-17", "linen-bag", 3), BuyerUpdate("buyer-8", "order-42", "buyer@example.com"), Decimal("2.50")
    )

    assert isinstance(result, HandoffResult)
    assert result.balance_ok is False
    assert result.handoff.order_id == "order-42"
    assert client.calls == [
        ("balance",),
        ("configure", Decimal("5"), Decimal("2.50")),
        ("email", "ops@example.com", Decimal("2.50")),
    ]
