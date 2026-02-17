import React from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  TooltipProps
} from 'recharts';
import { format, parseISO } from 'date-fns';
import { cn, formatPercent, formatNumber } from '../utils/format';
import EmptyState from './EmptyState';

interface ChartDataPoint {
  date: string;
  value: number;
  [key: string]: any;
}

interface FeatureChartProps {
  data: ChartDataPoint[];
  title: string;
  valueKey?: string;
  format?: 'number' | 'percent';
  color?: string;
  height?: number;
  className?: string;
  isLoading?: boolean;
}

const CustomTooltip: React.FC<TooltipProps<any, any> & { format?: 'number' | 'percent' }> = ({
  active,
  payload,
  label,
  format: formatType = 'number'
}) => {
  if (active && payload && payload.length) {
    const data = payload[0];
    return (
      <div className="bg-white dark:bg-neutral-800 p-3 border border-neutral-200 dark:border-neutral-700 rounded-lg shadow-lg">
        <p className="text-sm font-medium text-neutral-900 dark:text-neutral-100 mb-1">
          {format(parseISO(label), 'MMM d, yyyy')}
        </p>
        <p className="text-sm text-neutral-600 dark:text-neutral-400">
          <span className="font-medium" style={{ color: data.color }}>
            {formatType === 'percent' ? formatPercent(data.value) : formatNumber(data.value, 3)}
          </span>
        </p>
      </div>
    );
  }
  return null;
};

const FeatureChart: React.FC<FeatureChartProps> = ({
  data,
  title,
  valueKey = 'value',
  format = 'number',
  color = '#3b82f6',
  height = 300,
  className,
  isLoading = false
}) => {
  const formatXAxis = (tickItem: string) => {
    try {
      return format(parseISO(tickItem), 'MMM d');
    } catch {
      return tickItem;
    }
  };

  const formatYAxis = (value: number) => {
    if (format === 'percent') {
      return formatPercent(value, 0);
    }
    return formatNumber(value, 2);
  };

  if (isLoading) {
    return (
      <div className={cn('card', className)}>
        <h3 className="text-lg font-semibold text-neutral-900 dark:text-white mb-4">{title}</h3>
        <div className="animate-pulse">
          <div className="h-4 bg-neutral-200 dark:bg-neutral-700 rounded w-1/4 mb-4"></div>
          <div className={`bg-neutral-200 dark:bg-neutral-700 rounded`} style={{ height }}>
            <div className="flex items-end justify-around h-full p-4">
              {[...Array(7)].map((_, i) => (
                <div
                  key={i}
                  className="bg-neutral-300 dark:bg-neutral-600 rounded-t"
                  style={{ 
                    height: `${20 + Math.random() * 60}%`,
                    width: '8%'
                  }}
                />
              ))}
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (!data || data.length === 0) {
    return (
      <div className={cn('card', className)}>
        <h3 className="text-lg font-semibold text-neutral-900 dark:text-white mb-4">{title}</h3>
        <EmptyState height={height} title="No data available" message="Chart data will appear here when available" />
      </div>
    );
  }

  return (
    <div className={cn('card', className)}>
      <h3 className="text-lg font-semibold text-neutral-900 dark:text-white mb-4">{title}</h3>
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={data} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" className="[&>line]:stroke-neutral-200 dark:[&>line]:stroke-neutral-700" />
          <XAxis 
            dataKey="date" 
            tickFormatter={formatXAxis}
            stroke="#737373"
            fontSize={12}
          />
          <YAxis 
            tickFormatter={formatYAxis}
            stroke="#737373"
            fontSize={12}
          />
          <Tooltip content={<CustomTooltip format={format} />} />
          <Line
            type="monotone"
            dataKey={valueKey}
            stroke={color}
            strokeWidth={2}
            dot={{ fill: color, strokeWidth: 2, r: 4 }}
            activeDot={{ r: 6, stroke: color, strokeWidth: 2 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
};

export default FeatureChart;
