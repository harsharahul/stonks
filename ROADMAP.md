# Roadmap

What Stonks does today is in [README.md](README.md) and the [docs](docs/).
This file is what comes next, in rough order. Dates are not promised.

## Next

- **AI desk on demand.** Refresh a ticker from its page, event-triggered runs
  (earnings, filings, unusual volume), desk verdict badges on the watchlist,
  and a readable debate transcript.
- **More signal sources.** Automatic refresh of tracked 13F filings and a
  follow-any-fund option; government contract awards sized against market
  cap; insider cluster buys from Form 4; unusual options flow; the FDA
  decision calendar for biotech; post-earnings drift; retail attention from
  search trends.
- **Runtime-configurable frontend image.** OpenID Connect settings read at
  container start instead of build time, so the published image works with
  any provider without a rebuild.
- **Session hardening.** A backend-managed session (tokens never reach the
  browser) before the hosted service accepts live-brokerage links from
  people other than the operator, plus a Content-Security-Policy header.
- **Desk memory and reflection.** Past decisions feed the next run, a
  morning brief summarizes the overnight batch, and a replay view shows how a
  decision aged.

## Later

- Bring-your-own bots: API-driven and no-code strategies that act on the
  public signal stream.
- A backtest harness that replays desk decisions and strategies against
  historical prices.
- Real-time price streaming instead of hourly polling.
- Stock screener and side-by-side comparison.
- Optional hosted LLM tier for desk runs, evaluated against local models.
- Cross-ticker portfolio sizing across desk decisions.
- Push and email notifications for high-conviction alerts.
- Mobile-first redesign of the desk and dashboard.
- Vector search over the article store.
- Re-enable the full SEC filing parser once its dependencies install cleanly
  on current Python.
- Migrate the desk engine to the langchain and langgraph 1.x line.

## Not planned

- Live auto-copy trading. Mirrors stay on paper accounts.
- Paying strategy publishers.
- Any form of the platform placing orders without a user confirming them.
