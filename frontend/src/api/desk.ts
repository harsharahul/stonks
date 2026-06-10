/**
 * AI Trading Desk API client
 *
 * Routes mounted under /api/v1/desk.
 *   GET /desk/universe          List of covered tickers + decision badges
 *   GET /desk/{ticker}           Latest decision + briefs + outcome
 *   GET /desk/{ticker}/history   Past decisions for ticker
 */
import axios from 'axios';

import { getAccessToken } from './client';

const API_BASE_URL = (import.meta as any).env?.VITE_API_BASE_URL || '/api/v1';

const deskClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
});

// Attach the OIDC bearer token via the shared token bridge (NEVER read browser
// storage directly — tokens live in the react-oidc-context user and renew there).
deskClient.interceptors.request.use((config) => {
  const token = getAccessToken();
  if (token && config.url && !config.url.startsWith('http')) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface DeskDecisionRow {
  id: string;
  agent_run_id: string;
  ticker: string;
  as_of_date: string;
  decision: string;
  conviction: number;
  horizon_days: number | null;
  entry_price: number | null;
  stop_loss: number | null;
  take_profit: number | null;
  position_pct: number | null;
  thesis_text: string | null;
  top_risks_json: any;
  features_snapshot_json: any;
  pending: boolean;
  created_at: string;
}

export interface DeskBrief {
  id: string;
  agent_run_id: string;
  agent_name: string;
  round_index: number;
  output_json: any;
  output_text: string | null;
  conviction: number | null;
  tokens_in: number | null;
  tokens_out: number | null;
  created_at: string;
}

export interface DeskOutcome {
  id: string;
  agent_decision_id: string;
  evaluated_at: string;
  realized_return_5d: number | null;
  realized_return_30d: number | null;
  spy_return_5d: number | null;
  spy_return_30d: number | null;
  alpha_5d: number | null;
  alpha_30d: number | null;
  hit_stop: boolean | null;
  hit_target: boolean | null;
  reflection_text: string | null;
}

export interface DeskRun {
  id: string;
  ticker: string;
  run_started_at: string;
  run_completed_at: string | null;
  status: string;
  trigger: string;
  latency_ms: number | null;
  model: string | null;
  model_version: string | null;
  error: string | null;
  tokens_in_total: number | null;
  tokens_out_total: number | null;
}

export interface DeskUniverseRow {
  ticker: string;
  score: number | null;
  reason: string;
  included_at: string | null;
  latest_decision: DeskDecisionRow | null;
}

export interface DeskUniverseResponse {
  count: number;
  tickers: DeskUniverseRow[];
}

export interface DeskTickerView {
  ticker: string;
  as_of_date: string;
  run: DeskRun | null;
  decision: DeskDecisionRow;
  outcome: DeskOutcome | null;
  briefs: DeskBrief[];
}

export interface DeskHistoryResponse {
  ticker: string;
  count: number;
  decisions: Array<{
    decision: DeskDecisionRow;
    outcome: DeskOutcome | null;
  }>;
}

// ---------------------------------------------------------------------------
// Endpoints
// ---------------------------------------------------------------------------

export const deskApi = {
  async getUniverse(): Promise<DeskUniverseResponse> {
    const { data } = await deskClient.get<DeskUniverseResponse>('/desk/universe');
    return data;
  },

  async getDeskForTicker(ticker: string): Promise<DeskTickerView> {
    const { data } = await deskClient.get<DeskTickerView>(`/desk/${ticker.toUpperCase()}`);
    return data;
  },

  async getHistory(ticker: string, limit: number = 30): Promise<DeskHistoryResponse> {
    const { data } = await deskClient.get<DeskHistoryResponse>(
      `/desk/${ticker.toUpperCase()}/history`,
      { params: { limit } },
    );
    return data;
  },
};
