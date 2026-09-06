/**
 * Brokerage (Alpaca) API client.
 *
 * All routes require auth; the bearer token rides the same interceptor
 * pattern as the desk client. Credentials are sent ONCE at link time and
 * never come back from the API.
 */
import axios from 'axios';

import { getAccessToken } from './client';

const API_BASE_URL = (import.meta as any).env?.VITE_API_BASE_URL || '/api/v1';

const brokerClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
});

// Attach the OIDC bearer token via the shared token bridge (NEVER read browser
// storage directly: tokens live in the react-oidc-context user and renew there).
brokerClient.interceptors.request.use((config) => {
  const token = getAccessToken();
  if (token && config.url && !config.url.startsWith('http')) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface BrokerAccountRow {
  id: string;
  provider: string;
  paper: boolean;
  auto_execute: boolean;
  is_active: boolean;
  account_label: string | null;
  created_at: string | null;
  last_verified_at: string | null;
}

export interface BrokerInfo {
  account_number_masked: string | null;
  status: string;
  currency: string;
  cash: number | null;
  portfolio_value: number | null;
  buying_power: number | null;
  equity: number | null;
  daytrade_count: number | null;
  pattern_day_trader: boolean;
}

export interface BrokerAccountResponse {
  account: BrokerAccountRow;
  broker_info: BrokerInfo | null;
  market_open?: boolean | null;
  trading_halted?: boolean;
}

export interface BrokerPosition {
  symbol: string;
  qty: number;
  side: string;
  avg_entry_price: number | null;
  current_price: number | null;
  market_value: number | null;
  unrealized_pl: number | null;
  unrealized_plpc: number | null;
}

export interface BrokerOrderRow {
  id: string;
  symbol: string;
  side: string;
  qty: number | null;
  notional: number | null;
  order_type: string;
  time_in_force: string;
  limit_price: number | null;
  stop_loss_price: number | null;
  take_profit_price: number | null;
  status: string;
  paper: boolean;
  client_order_id: string;
  alpaca_order_id: string | null;
  filled_qty: number | null;
  filled_avg_price: number | null;
  source: string;
  source_ref: string | null;
  error: string | null;
  created_at: string | null;
  submitted_at: string | null;
  filled_at: string | null;
}

export interface PlaceOrderInput {
  symbol: string;
  side: 'buy' | 'sell';
  qty?: number;
  notional?: number;
  order_type?: 'market' | 'limit';
  limit_price?: number;
  time_in_force?: 'day' | 'gtc';
  stop_loss_price?: number;
  take_profit_price?: number;
  source?: 'manual' | 'desk' | 'signal';
  source_ref?: string;
  /** Idempotency ref: stable across retries of the same submission. */
  client_ref?: string;
  confirm_live?: boolean;
}

export interface SizingSuggestion {
  symbol: string;
  entry_price: number;
  equity: number;
  suggested_qty: number;
  suggested_value: number;
  suggested_stop_loss: number;
  suggested_take_profit: number;
}

// ---------------------------------------------------------------------------
// Endpoints
// ---------------------------------------------------------------------------

export const brokerApi = {
  async linkAccount(input: { api_key: string; secret_key: string; paper: boolean; confirm_live?: boolean }): Promise<BrokerAccountResponse> {
    const { data } = await brokerClient.post<BrokerAccountResponse>('/broker/account', input);
    return data;
  },

  async getAccount(): Promise<BrokerAccountResponse> {
    const { data } = await brokerClient.get<BrokerAccountResponse>('/broker/account');
    return data;
  },

  async unlinkAccount(): Promise<void> {
    await brokerClient.delete('/broker/account');
  },

  async getPositions(): Promise<{ positions: BrokerPosition[]; count: number }> {
    const { data } = await brokerClient.get('/broker/positions');
    return data;
  },

  async listOrders(limit = 50): Promise<{ orders: BrokerOrderRow[]; count: number }> {
    const { data } = await brokerClient.get('/broker/orders', { params: { limit } });
    return data;
  },

  async placeOrder(input: PlaceOrderInput): Promise<{ order: BrokerOrderRow; market_open: boolean }> {
    const { data } = await brokerClient.post('/broker/orders', input);
    return data;
  },

  async cancelOrder(orderId: string): Promise<{ order: BrokerOrderRow }> {
    const { data } = await brokerClient.delete(`/broker/orders/${orderId}`);
    return data;
  },

  async getSizing(symbol: string, stopLossPct = 0.05): Promise<SizingSuggestion> {
    const { data } = await brokerClient.get(`/broker/sizing/${symbol.toUpperCase()}`, {
      params: { stop_loss_pct: stopLossPct },
    });
    return data;
  },
};
