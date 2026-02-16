import React, { useState, useEffect, useMemo } from 'react';
import { Command } from 'cmdk';
import { useNavigate } from 'react-router-dom';
import * as Dialog from '@radix-ui/react-dialog';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  LayoutDashboard,
  TrendingUp,
  Brain,
  Zap,
  AlertTriangle,
  Search,
  RefreshCw,
  Keyboard,
  ArrowRight,
} from 'lucide-react';
import { stocksApi } from '../api/client';

interface CommandPaletteProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onShowShortcuts: () => void;
}

const allPages = [
  { to: '/', label: 'Dashboard', shortcut: 'Ctrl+1', icon: LayoutDashboard, keywords: ['home', 'main', 'overview'] },
  { to: '/stocks', label: 'Stocks', shortcut: 'Ctrl+2', icon: TrendingUp, keywords: ['list', 'watchlist', 'tickers'] },
  { to: '/intelligence', label: 'AI Intelligence', shortcut: 'Ctrl+3', icon: Brain, keywords: ['ai', 'analysis', 'sentiment', 'recommendations'] },
  { to: '/signals', label: 'Signals', shortcut: 'Ctrl+4', icon: Zap, keywords: ['trading', 'alerts', 'momentum'] },
  { to: '/anomalies', label: 'Anomalies', shortcut: 'Ctrl+5', icon: AlertTriangle, keywords: ['outliers', 'unusual', 'detection'] },
  { to: '/wsb-trending', label: 'WSB Trending', shortcut: 'Ctrl+6', icon: TrendingUp, keywords: ['reddit', 'wallstreetbets', 'meme'] },
];

const allActions = [
  { id: 'refresh', label: 'Refresh all data', icon: RefreshCw, keywords: ['reload', 'clear', 'cache'] },
  { id: 'shortcuts', label: 'Keyboard shortcuts', icon: Keyboard, shortcut: '?', keywords: ['help', 'keys', 'hotkeys'] },
];

const fuzzyMatch = (text: string, query: string): boolean => {
  const q = query.toLowerCase();
  const t = text.toLowerCase();
  return t.includes(q);
};

const useStockSearch = (query: string) => {
  const [debouncedQuery, setDebouncedQuery] = useState('');

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedQuery(query), 300);
    return () => clearTimeout(timer);
  }, [query]);

  return useQuery({
    queryKey: ['command-palette', 'stocks', debouncedQuery],
    queryFn: () => stocksApi.getStocks({ q: debouncedQuery, page_size: 8 }),
    enabled: debouncedQuery.length >= 1,
    staleTime: 60 * 1000,
    retry: 0,
  });
};

const itemClass = `flex items-center justify-between px-3 py-2.5 rounded-lg cursor-pointer text-sm
  text-neutral-700 data-[selected=true]:bg-blue-50 data-[selected=true]:text-blue-700 transition-colors`;

const CommandPalette: React.FC<CommandPaletteProps> = ({ open, onOpenChange, onShowShortcuts }) => {
  const [search, setSearch] = useState('');
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { data: stockResults, isLoading: stocksLoading } = useStockSearch(search);

  const stocks = stockResults?.items ?? [];

  const runAction = (fn: () => void) => {
    onOpenChange(false);
    fn();
  };

  // Filter pages and actions client-side
  const filteredPages = useMemo(() => {
    if (!search) return allPages;
    return allPages.filter(p =>
      fuzzyMatch(p.label, search) || p.keywords.some(k => fuzzyMatch(k, search))
    );
  }, [search]);

  const filteredActions = useMemo(() => {
    if (!search) return allActions;
    return allActions.filter(a =>
      fuzzyMatch(a.label, search) || a.keywords.some(k => fuzzyMatch(k, search))
    );
  }, [search]);

  const hasStockResults = search.length >= 1 && stocks.length > 0;
  const showNoResults = search.length >= 1 && filteredPages.length === 0 && filteredActions.length === 0 && !hasStockResults && !stocksLoading;

  // Reset search when dialog closes
  useEffect(() => {
    if (!open) setSearch('');
  }, [open]);

  return (
    <Command.Dialog
      open={open}
      onOpenChange={onOpenChange}
      label="Command palette"
      loop
      shouldFilter={false}
      overlayClassName="fixed inset-0 bg-black/50 backdrop-blur-sm z-[100]"
      contentClassName="fixed top-[20%] left-1/2 -translate-x-1/2 w-[calc(100%-2rem)] max-w-lg bg-white rounded-xl shadow-2xl border border-neutral-200 overflow-hidden z-[101]"
    >
      {/* Visually-hidden a11y elements for Radix Dialog */}
      <Dialog.Title className="sr-only">Command palette</Dialog.Title>
      <Dialog.Description className="sr-only">Search stocks, navigate pages, or run actions</Dialog.Description>

      {/* Search input */}
      <div className="flex items-center border-b border-neutral-200 px-4">
        <Search className="w-4 h-4 text-neutral-400 shrink-0" />
        <Command.Input
          value={search}
          onValueChange={setSearch}
          placeholder="Search stocks, pages, actions..."
          className="w-full py-3 px-3 text-sm outline-none placeholder-neutral-400 bg-transparent"
        />
        <kbd className="text-[10px] text-neutral-400 font-mono bg-neutral-100 px-1.5 py-0.5 rounded border border-neutral-200 shrink-0">
          Esc
        </kbd>
      </div>

      <Command.List className="max-h-[320px] overflow-y-auto p-2">
        {showNoResults && (
          <div className="px-4 py-8 text-center text-sm text-neutral-500">
            No results found.
          </div>
        )}

        {/* Stock results — shown first when searching to prioritize ticker matches */}
        {search.length >= 1 && (stocks.length > 0 || stocksLoading) && (
          <Command.Group
            heading={
              <span className="text-xs font-semibold text-neutral-500 uppercase tracking-wider px-2">
                Stocks {stocksLoading && '...'}
              </span>
            }
          >
            {stocks.map((stock) => (
              <Command.Item
                key={stock.symbol}
                value={`stock-${stock.symbol}`}
                onSelect={() => runAction(() => navigate(`/stocks/${stock.symbol}`))}
                className={itemClass}
              >
                <div className="flex items-center gap-2.5">
                  <span className="font-mono font-semibold text-blue-600 w-12">{stock.symbol}</span>
                  <span className="text-neutral-500 truncate max-w-[200px]">{stock.company_name}</span>
                </div>
                <ArrowRight className="w-3.5 h-3.5 text-neutral-300" />
              </Command.Item>
            ))}
          </Command.Group>
        )}

        {/* Pages */}
        {filteredPages.length > 0 && (
          <Command.Group
            heading={<span className="text-xs font-semibold text-neutral-500 uppercase tracking-wider px-2">Pages</span>}
          >
            {filteredPages.map((page) => (
              <Command.Item
                key={page.to}
                value={`page-${page.label}`}
                onSelect={() => runAction(() => navigate(page.to))}
                className={itemClass}
              >
                <div className="flex items-center gap-2.5">
                  <page.icon className="w-4 h-4 text-neutral-400" />
                  <span>{page.label}</span>
                </div>
                <kbd className="text-[10px] text-neutral-400 font-mono bg-neutral-100 px-1.5 py-0.5 rounded border border-neutral-200">
                  {page.shortcut}
                </kbd>
              </Command.Item>
            ))}
          </Command.Group>
        )}

        {/* Quick Actions */}
        {filteredActions.length > 0 && (
          <Command.Group
            heading={<span className="text-xs font-semibold text-neutral-500 uppercase tracking-wider px-2">Quick Actions</span>}
          >
            {filteredActions.map((action) => (
              <Command.Item
                key={action.id}
                value={`action-${action.id}`}
                onSelect={() => {
                  if (action.id === 'refresh') runAction(() => queryClient.invalidateQueries());
                  if (action.id === 'shortcuts') runAction(onShowShortcuts);
                }}
                className={itemClass}
              >
                <div className="flex items-center gap-2.5">
                  <action.icon className="w-4 h-4 text-neutral-400" />
                  <span>{action.label}</span>
                </div>
                {action.shortcut && (
                  <kbd className="text-[10px] text-neutral-400 font-mono bg-neutral-100 px-1.5 py-0.5 rounded border border-neutral-200">
                    {action.shortcut}
                  </kbd>
                )}
              </Command.Item>
            ))}
          </Command.Group>
        )}
      </Command.List>
    </Command.Dialog>
  );
};

export default CommandPalette;
