# Security

## Scope

Stonks is a self-hostable market terminal. The security-relevant surface is
narrow and deliberate:

- **Broker credentials.** Alpaca API keys are stored per user, encrypted at
  rest with a Fernet key the operator supplies (`BROKER_CREDS_ENCRYPTION_KEY`).
  Keys are never returned by any endpoint after linking. Paper trading is the
  default; live trading requires an explicit opt-in on the account link.
- **Order gates.** Every order passes pre-trade checks (symbol blocklists,
  tradability, liquidity floors, earnings proximity) that fail closed for live
  accounts. A global kill switch (`BROKER_TRADING_HALTED`) refuses all orders.
  Manual orders carry a client reference so a retried request cannot
  double-submit. Copy-trading mirrors are paper-only by design.
- **Identity.** Authentication is OpenID Connect with PKCE against an external
  provider; the frontend is a public client with no secret. The backend
  validates tokens against the provider's JWKS with the issuer and audience
  enforced. Admin rights come from an operator-managed allowlist, compared in
  constant time.
- **Input validation.** Ticker symbols are constrained at the path level.
  Preference payloads are size- and depth-limited. Rate limiting is on by
  default.

## Known limitations

- Access tokens live in the browser session (the standard SPA pattern). A
  cross-site scripting bug could read them. A backend-for-frontend session
  model is on the roadmap before the hosted service accepts live-brokerage
  links from strangers.
- The published frontend image bakes OIDC settings in at build time. Operators
  who use OIDC build the image themselves with the documented build arguments.
- Signal plugins run in-process. Only enable plugins you have reviewed.

## Supported versions

The latest minor release receives fixes. Older releases do not.

## Reporting a vulnerability

Email harsharahul@boggaram.net with a description and, where possible, a
reproduction. Please do not open a public issue for anything exploitable.
You will get an acknowledgement within a few days and a fix or a mitigation
plan before any public disclosure.
