# AI Trading Desk

The desk runs a multi-agent pipeline over each ticker in its universe and
records a decision with the reasoning that produced it. The agent roles and
their prompts come from the TradingAgents framework (vendored under
`app/agents/tradingagents/`, Apache 2.0); the data adapters, persistence, and
scheduling are Stonks-specific.

## Pipeline

1. **Analysts** (run in parallel): market (prices and indicators), social
   (news with sentiment), news (news, global news, insider and political
   trades), fundamentals (the distilled stock knowledge narrative).
2. **Researchers**: a bull and a bear argue from the analyst briefs.
3. **Research manager** weighs the debate into a thesis.
4. **Trader** turns the thesis into a proposed action.
5. **Risk debaters** (aggressive, conservative, neutral) stress the proposal.
6. **Portfolio manager** issues the decision and a conviction level.

Every brief and the final decision are stored (`agent_briefs`,
`agent_decisions`) along with the run metadata (`agent_runs`), so a decision
can be read back with its full trail.

## Inputs

Adapters in `app/agents/adapters/` read from the platform's own tables:
prices and technical indicators, news with sentiment, insider and political
trade signals, and fundamentals from the stock knowledge store. When a data
class is missing, the adapter returns a marked not-available block instead
of fabricating content, and the agents are told to rely on the narrative.

## Models

The desk uses two model tiers through Ollama by default: a quick model
(`OLLAMA_MODEL`) for analysts and debate, and a deep model
(`OLLAMA_DEEP_MODEL`) for the research manager, trader, and portfolio
manager. Calls stream, which keeps long generations alive through reverse
proxies with idle timeouts. `ANALYTICS_LLM_PROVIDER=openai` switches to the
OpenAI API with `OPENAI_API_KEY`.

## Universe and schedule

The universe is refreshed weekly (Sunday 00:00 UTC) from the union of user
watchlists, the largest one-day movers, and a reserve of broadly tracked
names, and is stored in `agent_universe_membership`. The nightly batch (07:15
UTC) runs every member. Outcomes are scored at 23:00 UTC by comparing each
decision with the subsequent price move (`agent_decision_outcomes`).

Desk tasks acknowledge late and are redelivered if a worker dies mid-run, so
a deployment restart does not lose the night's batch. They run on the
`analytics` queue, isolated from ingestion.

## Endpoints and UI

- `GET /api/v1/desk/universe`: covered tickers with their latest decision.
- `GET /api/v1/desk/{ticker}`: latest decision, briefs, and scored outcome.
- `GET /api/v1/desk/{ticker}/history`: past decisions with realized results.
- `/desk` and `/desk/:ticker` in the UI show the decision, the briefs, and
  the outcome record; the stock detail page links to it.
- The admin console can refresh the universe, run the nightly batch, run a
  single ticker, and score outcomes on demand.

Orders placed from a desk decision carry that decision's id in the order
ledger, so the trail runs from analysis to fill.

## Modifications to the vendored framework

`app/agents/tradingagents/NOTICE` lists the pinned upstream commit and each
local change. Changes are kept minimal so the framework can be re-vendored.
