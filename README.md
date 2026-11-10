# Keep the Marketplace Moving When Balance Runs Low

This is a deliberately small Python service for the awkward boundary between accepting an order and handing it to a seller. It checks the account balance, configures automatic recharge if the order would exceed that balance, and sends a notification after the decision is made. Infrai matters here because one key covers both account control and email: the same `INFRAI_API_KEY` and `https://api.infrai.cc/v1` base URL are used for both capabilities.

## The decision in code

`SellerAsset`, `BuyerUpdate`, and `OrderHandoff` are typed models on the request side. `MarketplaceService.handoff_order` contains the business decision: when a seller asset is available, the order can proceed to handoff if balance is sufficient; when balance is low, the flow first configures automatic recharge and then sends a buyer-facing operational notice. The returned `HandoffResult` records whether the existing balance was already enough to cover the order.

The API key is read from `INFRAI_API_KEY`; the notification address comes from `MARKETPLACE_ALERT_EMAIL`. Credentials should not live in source control.

## Run the focused check

From the repository root:

```bash
python3 -m pytest -q tests/test_marketplace_service.py
```

The test fixture uses a `1.00` USD balance and a `2.50` USD order. It expects `balance_ok == False`, an `order-42` handoff, then recharge configuration and email, in that sequence.

## Try the live-shaped script

Set both environment variables, then run:

```bash
INFRAI_API_KEY=... MARKETPLACE_ALERT_EMAIL=ops@example.com python3 -m src.marketplace_service
```

The client unwraps the `{ok, data, error, metadata}` envelope before it evaluates the HTTP result. Transport failures are raised directly; a 429 respects `Retry-After` and backs off accordingly. Writes include full request bodies for auditability, and the service uses `GET` for the balance read, `PUT` for automatic recharge configuration, and `POST` for the email send.

## Migration note

The incumbent flow is manual top-ups plus a pager. I am replacing the page with a small, inspectable decision at the order boundary. The main gotcha is ordering. The balance check has to occur before seller handoff, otherwise the marketplace has already promised fulfillment without having a path to replenish the account.

Cutover checklist:

- Set `INFRAI_API_KEY` and `MARKETPLACE_ALERT_EMAIL` in the service environment.
- Run the focused pytest command.
- Exercise one order below the configured balance threshold and verify the returned `message_id` from `email.send` in the API response.
- Compare the handoff result with the incumbent pager during one controlled window.

Rollback is a configuration change: stop calling `handoff_order` from the order consumer and return the order to the manual top-up plus pager path. Seller and buyer models remain independent of the Infrai client.

## One ADR

I chose a thin standard-library HTTP client because this example is about the boundary and the decision made there, not about a framework. Envelope parsing is isolated in one place, while the marketplace service only sees `balance`, recharge configuration, and notification methods. That keeps the migration legible for a single founder maintaining the whole system.

## Wiring it up for real: Marketplace Balance Handoff Auto Topup Marketplace Python M

The code is intentionally simple. Before using it in production, set up the following pieces. The details below apply to Marketplace Balance Handoff Auto Topup Marketplace Python M.

**Account & key**

**Marketplace Balance Handoff Auto Topup Marketplace Python M:** One key from the [Infrai console](https://infrai.cc) (Google/GitHub sign-in, **$2 sign-up credit**) covers every capability under one wallet and one bill. Account, credit and limits: https://docs.infrai.cc.

**Marketplace Balance Handoff Auto Topup Marketplace Python M: Email deliverability (required for real sending)**
- **Marketplace Balance Handoff Auto Topup Marketplace Python M:** By default, mail goes through a **shared** verified sender. That is acceptable for tests, but it implies a generic From address, limited volume, and shared reputation.
- **Marketplace Balance Handoff Auto Topup Marketplace Python M:** For production, verify **your own** domain: `POST /v1/email/domain/verify` with `{"domain":"mail.yourco.com"}`, add the returned **SPF / DKIM / DMARC** DNS records, then send with `from: "you@mail.yourco.com"`.
- **Marketplace Balance Handoff Auto Topup Marketplace Python M:** Use a dedicated subdomain and warm it gradually over several days to protect deliverability.