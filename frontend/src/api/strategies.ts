/**
 * Strategies API — the social layer.
 * Trade feeds are privacy-reduced server-side (no qty/notional ever).
 */
import apiClient from './client';

export interface StrategyPerf {
  date: string | null;
  paper: boolean;
  trade_count: number;
  closed_trade_count: number;
  win_count: number;
  win_rate: number | null;
  realized_pnl: number | null;
  avg_return_pct: number | null;
  max_drawdown_pct: number | null;
}

export interface StrategySummary {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  visibility: 'private' | 'unlisted' | 'public';
  kind: string;
  disclosure: string | null;
  is_active: boolean;
  created_at: string | null;
  follower_count?: number;
  performance?: StrategyPerf | null;
}

export interface StrategyTrade {
  symbol: string;
  side: string;
  order_type: string;
  status: string;
  paper: boolean;
  filled_avg_price: number | null;
  at: string | null;
}

export interface StrategyDetailResponse {
  strategy: StrategySummary;
  is_owner: boolean;
  is_following: boolean;
  follower_count: number;
  performance: StrategyPerf[];
  trades: StrategyTrade[];
  disclaimer: string;
}

export const strategiesApi = {
  async discover(): Promise<{ strategies: StrategySummary[]; disclaimer: string }> {
    const r = await apiClient.get('/strategies/public');
    return r.data;
  },
  async mine(): Promise<{ strategies: StrategySummary[] }> {
    const r = await apiClient.get('/strategies/mine');
    return r.data;
  },
  async following(): Promise<{ following: (StrategySummary & { copy_mode: string })[] }> {
    const r = await apiClient.get('/strategies/following/mine');
    return r.data;
  },
  async detail(slug: string): Promise<StrategyDetailResponse> {
    const r = await apiClient.get(`/strategies/${slug}`);
    return r.data;
  },
  async create(body: { name: string; description?: string; visibility: string; disclosure?: string }) {
    const r = await apiClient.post('/strategies', body);
    return r.data;
  },
  async follow(slug: string) {
    const r = await apiClient.post(`/strategies/${slug}/follow`, { copy_mode: 'notify' });
    return r.data;
  },
  async unfollow(slug: string) {
    const r = await apiClient.delete(`/strategies/${slug}/follow`);
    return r.data;
  },
};
