# Broker, orders, and strategies

Stonks places orders through the user's own Alpaca account. The platform
holds no funds and never places an order that a signed-in user did not
confirm.

## Linking an account

`POST /api/v1/broker/account` stores an Alpaca key pair for the signed-in
user, encrypted at rest with Fernet under `BROKER_CREDS_ENCRYPTION_KEY`.
Accounts are paper by default; a live account must be flagged explicitly on
link. `GET` returns the account summary (equity, cash, buying power) without
the keys; `PATCH` changes settings such as the copy-trading opt-in; `DELETE`
unlinks.

## Orders

- `GET /api/v1/broker/positions` and `GET /api/v1/broker/orders` mirror the
  broker state.
- `POST /api/v1/broker/orders` places a market or limit order, optionally as
  a bracket with stop-loss and take-profit. Each request carries a client
  reference; the same reference replays the original result instead of
  submitting twice.
- `DELETE /api/v1/broker/orders/{order_id}` cancels.
- `GET /api/v1/broker/sizing/{symbol}` suggests a size from the account's
  risk budget.

Every order passes the sanity gates in `app/services/broker/sanity.py`:
symbol blocklists, tradability, liquidity floors, and earnings proximity.
Gates fail closed for live accounts. `BROKER_TRADING_HALTED=true` refuses
every order platform-wide.

The trade ticket appears on the stock detail page, on the desk decision
header, and behind each consolidated ranking. It is prefilled, never
auto-submitted. Orders from a desk decision record that decision's id.

## Strategies

A strategy is a named, followable stream of a user's orders.

- `POST /api/v1/strategies` creates one; `PUT /api/v1/strategies/{slug}`
  edits it. Public strategies require a disclosure statement.
- Orders are tagged to a strategy at placement; desk-originated orders are
  tagged automatically to the platform's desk strategy.
- `GET /api/v1/strategies/public` lists public strategies ranked by
  objective performance; `GET /api/v1/strategies/{slug}` shows the verified
  record and a privacy-reduced trade feed that never exposes quantities or
  notional amounts.
- `POST` and `DELETE /api/v1/strategies/{slug}/follow` follow and unfollow;
  `GET /api/v1/strategies/mine` and `/following/mine` list the user's own.

Performance is computed nightly (23:30 UTC) from real fills with FIFO
matching into `strategy_performance_daily`: win rate, average return, and
maximum drawdown, shown with the mandatory disclaimers.

## Copy trading (paper only)

A follower with a paper account and `auto_execute` enabled can mirror a
strategy's trades. The mirror task is idempotent (a deterministic client
order id per follower and origin order), sizes from the follower's own
equity with a ten percent cap per position, and on a sell closes only the
position that was mirrored. Mirrors carry no strategy tag of their own. Live
accounts cannot enable auto-execute.
