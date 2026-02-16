export interface ScreenerFilters {
  sentimentMin: number;
  sentimentMax: number;
  returnsMin: number;
  returnsMax: number;
  minArticles: number;
  activityLevels: string[]; // 'High' | 'Med' | 'Low', empty = all
}

export const DEFAULT_SCREENER_FILTERS: ScreenerFilters = {
  sentimentMin: 0,
  sentimentMax: 1,
  returnsMin: -1,
  returnsMax: 1,
  minArticles: 0,
  activityLevels: [],
};

export const isScreenerActive = (filters: ScreenerFilters): boolean => {
  const d = DEFAULT_SCREENER_FILTERS;
  return (
    filters.sentimentMin !== d.sentimentMin ||
    filters.sentimentMax !== d.sentimentMax ||
    filters.returnsMin !== d.returnsMin ||
    filters.returnsMax !== d.returnsMax ||
    filters.minArticles !== d.minArticles ||
    filters.activityLevels.length > 0
  );
};

interface StockLike {
  latest_features: {
    sentiment: number | null;
    returns_5d: number | null;
    article_count: number;
  } | null;
}

export const passesScreenerFilters = (
  stock: StockLike,
  filters: ScreenerFilters,
  activityLevel: string,
): boolean => {
  const f = stock.latest_features;

  // Sentiment filter (skip stocks with no data only if filter is narrowed)
  const sentiment = f?.sentiment ?? null;
  if (sentiment !== null) {
    if (sentiment < filters.sentimentMin || sentiment > filters.sentimentMax) return false;
  } else if (filters.sentimentMin > 0 || filters.sentimentMax < 1) {
    return false; // No data and filter is active — exclude
  }

  // Returns filter
  const ret = f?.returns_5d ?? null;
  if (ret !== null) {
    if (ret < filters.returnsMin || ret > filters.returnsMax) return false;
  } else if (filters.returnsMin > -1 || filters.returnsMax < 1) {
    return false;
  }

  // Min articles
  const articles = f?.article_count ?? 0;
  if (articles < filters.minArticles) return false;

  // Activity level toggle
  if (filters.activityLevels.length > 0) {
    if (!filters.activityLevels.includes(activityLevel)) return false;
  }

  return true;
};
