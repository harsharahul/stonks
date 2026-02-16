import { useMemo, useCallback } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useFeaturesSummary, useFeatureStats } from './useFeatures';
import { useTomorrowOutlook, useDailyRecommendations } from './useMarketIntelligence';
import {
  useLatestAlerts, useMarketAnomalies, useWSBTrending, useSentimentAnalysis,
} from './useWSBDashboard';
import { feedApi } from '../api/client';

export const useDashboard = () => {
  // Existing dashboard data
  const featuresSummary = useFeaturesSummary(undefined, 20);
  const featureStats = useFeatureStats(7);

  // New data sources
  const outlook = useTomorrowOutlook();
  const recommendations = useDailyRecommendations();
  const alerts = useLatestAlerts(12);
  const anomalies = useMarketAnomalies();
  const wsbTrending = useWSBTrending(7, 5);
  const sentiment = useSentimentAnalysis();
  const articles = useQuery({
    queryKey: ['dashboard-articles'],
    queryFn: () => feedApi.getArticles({ page_size: 8 }),
    staleTime: 2 * 60 * 1000,
    retry: 1,
  });

  // Derived data
  const topGainers = useMemo(() =>
    featuresSummary.data?.features
      ?.filter((s) => s.ret_5d !== null)
      .sort((a, b) => (b.ret_5d || 0) - (a.ret_5d || 0))
      .slice(0, 5) || [],
    [featuresSummary.data],
  );

  const topLosers = useMemo(() =>
    featuresSummary.data?.features
      ?.filter((s) => s.ret_5d !== null)
      .sort((a, b) => (a.ret_5d || 0) - (b.ret_5d || 0))
      .slice(0, 5) || [],
    [featuresSummary.data],
  );

  const sentimentLeaders = useMemo(() =>
    featuresSummary.data?.features
      ?.filter((s) => s.sent_mean_7d !== null)
      .sort((a, b) => (b.sent_mean_7d || 0) - (a.sent_mean_7d || 0))
      .slice(0, 5) || [],
    [featuresSummary.data],
  );

  const refreshAll = useCallback(() => {
    featuresSummary.refetch();
    featureStats.refetch();
    outlook.refetch();
    recommendations.refetch();
    alerts.refetch();
    anomalies.refetch();
    wsbTrending.refetch();
    sentiment.refetch();
    articles.refetch();
  }, [featuresSummary, featureStats, outlook, recommendations, alerts, anomalies, wsbTrending, sentiment, articles]);

  return {
    featuresSummary,
    featureStats,
    outlook,
    recommendations,
    alerts,
    anomalies,
    wsbTrending,
    sentiment,
    articles,
    topGainers,
    topLosers,
    sentimentLeaders,
    refreshAll,
  };
};
