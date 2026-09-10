# Changelog

All notable changes to Stonks are documented here, following
[Keep a Changelog](https://keepachangelog.com/) and semantic versioning.

## [Unreleased]

## [2.0.2] - 2026-09-10

### Fixed
- Backfilled prices are visible to scoring within the same run. The scorer
  read prices through a fresh database session, so bars it had just written
  for a previously unpriced ticker were not seen until a later run. It now
  reads within the run's session, so a ticker backfilled from the market data
  source is scored immediately.

## [2.0.1] - 2026-09-10

### Fixed
- Signal outcomes are durable: the outcome record now survives deletion of the
  signal it scored (foreign key set null on delete, not cascade), and signal
  cleanup retains signals past the scoring window instead of removing them
  after seven days, so a track record is never lost to housekeeping.
- Signal outcome scoring walks the whole pending set in pages instead of
  one fixed batch of the oldest rows, so signals that cannot be priced yet no
  longer block the ones behind them. Prices are read once per ticker per run,
  and tickers outside the tracked stock list are backfilled from the market
  data source so every directional signal earns a track record.

## [2.0.0] - 2026-09-08

First public release, under the AGPL-3.0 license. The major version marks
three changes that need attention when upgrading from 1.16.0: signal source
identifiers for the tracked-figure plugins change (a migration carries the
scored history across), the container images move to `ghcr.io/harsharahul`,
and the Kubernetes manifests leave the source tree. See `docs/deployment.md`.

### Added
- Database bootstrap on container start: waits for PostgreSQL, creates the
  schema on an empty database, migrates an existing one, and seeds a starter
  universe, so `docker compose up` on a fresh clone yields a working app.
- Per-source plugin configuration from the environment (`SIGNAL_SOURCE_CONFIG`)
  and from the admin API (`PUT /admin/signal-sources/{id}/config`).
- Open-source release: AGPL-3.0 license, contribution guide, security policy,
  code of conduct, contributor license agreement, third-party notices,
  references, GitHub Actions CI publishing multi-architecture images to
  ghcr.io, Dependabot, and present-tense documentation under `docs/`.
- `SEC_CONTACT_EMAIL` setting, declared to SEC EDGAR as the fair-access
  policy requires.
- A single `VERSION` file drives the API version and is checked against the
  frontend package and the release tag.
- `pytest.ini` scopes the unit suite to `tests/`; the integration scripts
  under `scripts/` need a running database and are run by hand.

### Changed
- The three tracked-figure signal sources are now generic and configurable:
  `public_figure_mentions`, `board_seat_tracker`, and `fund_13f_tracker`
  read who and what they track from `SIGNAL_SOURCE_CONFIG` or the admin
  console instead of lists in code. Existing deployments carry their track
  records across by setting `SIGNAL_SOURCE_RENAMES` before migrating.
- One backend image (`Dockerfile.backend`) and one frontend image
  (`Dockerfile.frontend`); the separate API and worker Dockerfiles are gone.
- Frontend image builds on Node 22.
- Legacy planning documents removed from the tree.

### Security
- aiohttp 3.14.3 and langchain 0.3.30. The remaining advisories on the
  langchain and langgraph 0.3 line are fixed only by the 1.x migration and
  are listed explicitly in the CI audit step until then.

### Fixed
- Consolidated rankings cache stores the full computation and slices per
  request, so different page sizes no longer return inconsistent lists.

## [1.16.0] - 2026-06-11

### Added
- Two signal sources: board-seat positioning around a tracked public figure,
  and the 13F holdings of a tracked AI-infrastructure fund with filing-age
  decay.
- Live collection counts per signal source (active and last seven days) in
  the admin console.

### Changed
- Congressional-trade scoring upgraded to a six-factor model with polite
  handling of rate limits.
- Public-figure news scanner adapted to the current yfinance news shape.

## [1.15.0] - 2026-06-11

### Changed
- Navigation grouped by function (market data, intelligence, trading,
  account) across desktop and mobile.

### Fixed
- Several UI defects found in end-to-end browser testing.
- Hardening for provider outages: ingestion tasks skip and report instead of
  failing the batch.

## [1.14.0] - 2026-06-11

### Added
- Consolidated rankings: signal consensus weighted by each source's verified
  record, desk verdict and conviction, and the quantitative recommendation
  blended into one score per ticker with the breakdown shown. Dashboard panel
  with a one-click prefilled trade ticket.
- Win-rate badges wherever signals are listed.
- Manual orders carry a client reference, so a retried request is idempotent.

### Changed
- The analytics fallback when the LLM is unavailable is now marked as such
  in the response and the UI.

### Removed
- The unused intelligent-signals endpoints and workflow stubs.

## [1.13.0] - 2026-06-10

### Added
- Per-source signal track records: a nightly scorer records each signal's
  five-day realized return; win rate and average return per source are public
  and shown in the admin console.

### Fixed
- SEC EDGAR ingestion and CIK-to-ticker mapping are scheduled again.
- Article metadata is persisted for earnings, filings, and Reddit sources
  (a keyword mismatch had dropped it silently).
- The earnings calendar no longer substitutes placeholder rows outside the
  development environment.

## [1.12.0] - 2026-06-10

### Added
- Strategies: publish a strategy, tag orders to it, follow others, and see
  nightly verified track records with disclosures. Public strategy pages.
- Paper-only copy engine: followers can mirror a strategy's trades into
  their own paper account with independent sizing and a hard cap.
- Separate worker processes for LLM analytics and for fast ingestion queues,
  so desk runs no longer delay ingestion.

## [1.11.0] - 2026-06-10

### Added
- Signal source plugin SDK: a registry decorator, a dispatcher that runs
  enabled sources every thirty minutes with fingerprint deduplication, admin
  toggles per source, and three bundled sources (Reddit momentum,
  congressional trades, tracked public-figure news).

### Fixed
- Logout completes cleanly at the identity provider.

## [1.10.0] - 2026-06-09

### Added
- Reddit ingestion authenticates with the Reddit API.
- Desk run tasks survive worker restarts and show honest job history.
- Per-ticker desk run from the admin console.

### Security
- Dependency upgrade pass across the web framework, token library, HTTP
  client, XML parser, and LLM client.

## [1.9.6] - 2026-06-09

### Fixed
- Stock detail crash when the tracked list was empty.
- Ingress accepts additional external hostnames.

## [1.9.5] - 2026-06-09

### Fixed
- Desk universe selection read a feature column that did not exist, leaving
  the features snapshot empty in every run.

## [1.9.4] - 2026-06-09

### Added
- AI desk tasks (universe refresh, nightly batch, outcome scoring) in the
  admin task catalog with Run Now and parameters.

## [1.9.3] - 2026-06-09

### Fixed
- Sessions renew silently instead of expiring after minutes.
- Long-running LLM endpoints no longer block the API; the insights endpoint
  redirects to the precomputed desk decision.
- Anomaly detection repaired; watch any symbol with automatic backfill.

## [1.9.2] - 2026-06-09

### Added
- Multi-architecture container images (amd64 and arm64).
