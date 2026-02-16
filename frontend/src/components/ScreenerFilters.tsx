import React, { useState } from 'react';
import { SlidersHorizontal, RotateCcw, ChevronDown, ChevronUp } from 'lucide-react';
import { cn } from '../utils/format';
import { ScreenerFilters, DEFAULT_SCREENER_FILTERS, isScreenerActive } from '../hooks/useStockScreener';

interface ScreenerFiltersPanelProps {
  filters: ScreenerFilters;
  onChange: (filters: ScreenerFilters) => void;
  filteredCount: number;
  totalCount: number;
}

const activityOptions = ['High', 'Med', 'Low'] as const;

const RangeSlider: React.FC<{
  label: string;
  min: number;
  max: number;
  step: number;
  value: [number, number];
  onChange: (value: [number, number]) => void;
  formatValue?: (v: number) => string;
}> = ({ label, min, max, step, value, onChange, formatValue = (v) => v.toString() }) => {
  const pctLeft = ((value[0] - min) / (max - min)) * 100;
  const pctRight = ((value[1] - min) / (max - min)) * 100;

  return (
    <div>
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-xs font-medium text-neutral-600">{label}</span>
        <span className="text-xs text-neutral-500 font-mono">
          {formatValue(value[0])} — {formatValue(value[1])}
        </span>
      </div>
      {/* Visual range bar */}
      <div className="relative h-1.5 bg-neutral-200 rounded-full mb-2">
        <div
          className="absolute h-1.5 bg-blue-500 rounded-full"
          style={{ left: `${pctLeft}%`, width: `${pctRight - pctLeft}%` }}
        />
      </div>
      {/* Dual range inputs */}
      <div className="relative h-5">
        <input
          type="range"
          min={min}
          max={max}
          step={step}
          value={value[0]}
          onChange={(e) => {
            const v = parseFloat(e.target.value);
            if (v <= value[1]) onChange([v, value[1]]);
          }}
          className="absolute inset-0 w-full appearance-none bg-transparent pointer-events-none [&::-webkit-slider-thumb]:pointer-events-auto [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3.5 [&::-webkit-slider-thumb]:h-3.5 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-blue-600 [&::-webkit-slider-thumb]:border-2 [&::-webkit-slider-thumb]:border-white [&::-webkit-slider-thumb]:shadow-sm [&::-webkit-slider-thumb]:cursor-pointer"
        />
        <input
          type="range"
          min={min}
          max={max}
          step={step}
          value={value[1]}
          onChange={(e) => {
            const v = parseFloat(e.target.value);
            if (v >= value[0]) onChange([value[0], v]);
          }}
          className="absolute inset-0 w-full appearance-none bg-transparent pointer-events-none [&::-webkit-slider-thumb]:pointer-events-auto [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3.5 [&::-webkit-slider-thumb]:h-3.5 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-blue-600 [&::-webkit-slider-thumb]:border-2 [&::-webkit-slider-thumb]:border-white [&::-webkit-slider-thumb]:shadow-sm [&::-webkit-slider-thumb]:cursor-pointer"
        />
      </div>
    </div>
  );
};

const ScreenerFiltersPanel: React.FC<ScreenerFiltersPanelProps> = ({
  filters,
  onChange,
  filteredCount,
  totalCount,
}) => {
  const [expanded, setExpanded] = useState(false);
  const active = isScreenerActive(filters);

  return (
    <div className="bg-white rounded-xl border border-neutral-200 shadow-sm">
      {/* Collapse bar */}
      <button
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center justify-between px-4 py-3 text-sm font-medium text-neutral-700 hover:bg-neutral-50 transition-colors rounded-xl"
      >
        <div className="flex items-center gap-2">
          <SlidersHorizontal className="w-4 h-4 text-neutral-500" />
          <span>Screener</span>
          {active && (
            <span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full font-medium">
              {filteredCount} / {totalCount}
            </span>
          )}
        </div>
        {expanded ? (
          <ChevronUp className="w-4 h-4 text-neutral-400" />
        ) : (
          <ChevronDown className="w-4 h-4 text-neutral-400" />
        )}
      </button>

      {/* Expanded filters */}
      {expanded && (
        <div className="px-4 pb-4 pt-1 border-t border-neutral-100">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5 mt-3">
            {/* Sentiment range */}
            <RangeSlider
              label="Sentiment"
              min={0}
              max={1}
              step={0.05}
              value={[filters.sentimentMin, filters.sentimentMax]}
              onChange={([min, max]) => onChange({ ...filters, sentimentMin: min, sentimentMax: max })}
              formatValue={(v) => v.toFixed(2)}
            />

            {/* 5d Return range */}
            <RangeSlider
              label="5d Return"
              min={-1}
              max={1}
              step={0.05}
              value={[filters.returnsMin, filters.returnsMax]}
              onChange={([min, max]) => onChange({ ...filters, returnsMin: min, returnsMax: max })}
              formatValue={(v) => `${(v * 100).toFixed(0)}%`}
            />

            {/* Min articles */}
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-xs font-medium text-neutral-600">Min Articles</span>
                <span className="text-xs text-neutral-500 font-mono">{filters.minArticles}</span>
              </div>
              <div className="relative h-1.5 bg-neutral-200 rounded-full mb-2">
                <div
                  className="h-1.5 bg-blue-500 rounded-full"
                  style={{ width: `${(filters.minArticles / 50) * 100}%` }}
                />
              </div>
              <input
                type="range"
                min={0}
                max={50}
                step={1}
                value={filters.minArticles}
                onChange={(e) => onChange({ ...filters, minArticles: parseInt(e.target.value) })}
                className="w-full appearance-none bg-transparent [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3.5 [&::-webkit-slider-thumb]:h-3.5 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-blue-600 [&::-webkit-slider-thumb]:border-2 [&::-webkit-slider-thumb]:border-white [&::-webkit-slider-thumb]:shadow-sm [&::-webkit-slider-thumb]:cursor-pointer [&::-webkit-slider-runnable-track]:h-0"
              />
            </div>

            {/* Activity level toggles */}
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-xs font-medium text-neutral-600">Activity Level</span>
              </div>
              <div className="flex gap-1.5 mt-2">
                {activityOptions.map((level) => {
                  const selected = filters.activityLevels.includes(level);
                  return (
                    <button
                      key={level}
                      onClick={() => {
                        const next = selected
                          ? filters.activityLevels.filter((l) => l !== level)
                          : [...filters.activityLevels, level];
                        onChange({ ...filters, activityLevels: next });
                      }}
                      className={cn(
                        'px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors',
                        selected
                          ? 'bg-blue-600 text-white border-blue-600'
                          : 'bg-white text-neutral-600 border-neutral-200 hover:border-neutral-300'
                      )}
                    >
                      {level}
                    </button>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Reset button */}
          {active && (
            <div className="mt-4 flex justify-end">
              <button
                onClick={() => onChange({ ...DEFAULT_SCREENER_FILTERS })}
                className="flex items-center gap-1.5 text-xs text-neutral-500 hover:text-neutral-700 transition-colors"
              >
                <RotateCcw className="w-3 h-3" />
                Reset all filters
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default ScreenerFiltersPanel;
