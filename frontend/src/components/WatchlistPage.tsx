import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Link, useNavigate } from 'react-router-dom';
import { watchlistApi, WatchlistItem } from '../api/client';
import { useAuth } from '../hooks/useAuth';
import { Star, Trash2, Plus, Search, StickyNote } from 'lucide-react';
import { cn } from '../utils/format';

const WatchlistPage: React.FC = () => {
  const { isAuthenticated, login, isOidcEnabled } = useAuth();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [addSymbol, setAddSymbol] = useState('');
  const [addError, setAddError] = useState('');

  const { data, isLoading, error } = useQuery({
    queryKey: ['watchlist'],
    queryFn: () => watchlistApi.getWatchlist(),
    enabled: isAuthenticated,
  });

  const addMutation = useMutation({
    mutationFn: (symbol: string) => watchlistApi.addToWatchlist(symbol),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['watchlist'] });
      setAddSymbol('');
      setAddError('');
    },
    onError: (err: any) => {
      setAddError(err.response?.data?.detail || 'Failed to add stock');
    },
  });

  const removeMutation = useMutation({
    mutationFn: (symbol: string) => watchlistApi.removeFromWatchlist(symbol),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['watchlist'] }),
  });

  // Guard: not logged in
  if (!isAuthenticated) {
    return (
      <div className="max-w-2xl mx-auto mt-20 text-center px-4">
        <Star className="w-12 h-12 mx-auto text-neutral-300 dark:text-neutral-600 mb-4" />
        <h2 className="text-xl font-semibold text-neutral-800 dark:text-white mb-2">Your Watchlist</h2>
        <p className="text-neutral-500 dark:text-neutral-400 mb-6">Sign in to save and track your favourite stocks.</p>
        {isOidcEnabled && (
          <button onClick={login} className="px-5 py-2 rounded-lg bg-blue-600 text-white hover:bg-blue-700 font-medium text-sm">
            Sign In
          </button>
        )}
      </div>
    );
  }

  const items: WatchlistItem[] = data?.watchlist ?? [];

  return (
    <div className="max-w-4xl mx-auto px-4 py-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-neutral-900 dark:text-white flex items-center gap-2">
          <Star className="w-6 h-6 text-yellow-500" /> Watchlist
          {data && <span className="text-base font-normal text-neutral-400">({data.count})</span>}
        </h1>
      </div>

      {/* Add stock form */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (addSymbol.trim()) addMutation.mutate(addSymbol.trim().toUpperCase());
        }}
        className="flex gap-2 mb-6"
      >
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-neutral-400" />
          <input
            type="text"
            value={addSymbol}
            onChange={(e) => { setAddSymbol(e.target.value); setAddError(''); }}
            placeholder="Add a symbol (e.g. AAPL)"
            className="w-full pl-9 pr-3 py-2 border border-neutral-200 dark:border-neutral-700 rounded-lg bg-white dark:bg-neutral-800 text-sm text-neutral-900 dark:text-white placeholder-neutral-400 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>
        <button
          type="submit"
          disabled={addMutation.isLoading || !addSymbol.trim()}
          className="px-4 py-2 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-50 flex items-center gap-1"
        >
          <Plus className="w-4 h-4" /> Add
        </button>
      </form>
      {addError && <p className="text-sm text-red-500 mb-4 -mt-4">{addError}</p>}

      {/* Loading */}
      {isLoading && (
        <div className="text-center py-12 text-neutral-500">Loading watchlist...</div>
      )}

      {/* Error */}
      {error && (
        <div className="text-center py-12 text-red-500">
          Failed to load watchlist. Try refreshing.
        </div>
      )}

      {/* Empty */}
      {!isLoading && !error && items.length === 0 && (
        <div className="text-center py-16">
          <Star className="w-10 h-10 mx-auto text-neutral-300 dark:text-neutral-600 mb-3" />
          <p className="text-neutral-500 dark:text-neutral-400">No stocks in your watchlist yet. Add one above.</p>
        </div>
      )}

      {/* Watchlist table */}
      {items.length > 0 && (
        <div className="bg-white dark:bg-neutral-800 border border-neutral-200 dark:border-neutral-700 rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-neutral-200 dark:border-neutral-700 text-left text-neutral-500 dark:text-neutral-400 text-xs uppercase">
                <th className="px-4 py-3">Symbol</th>
                <th className="px-4 py-3 hidden sm:table-cell">Company</th>
                <th className="px-4 py-3 hidden md:table-cell">Notes</th>
                <th className="px-4 py-3 hidden md:table-cell">Added</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr
                  key={item.id}
                  className="border-b last:border-b-0 border-neutral-100 dark:border-neutral-700/50 hover:bg-neutral-50 dark:hover:bg-neutral-700/30 cursor-pointer"
                  onClick={() => item.symbol && navigate(`/stocks/${item.symbol}`)}
                >
                  <td className="px-4 py-3 font-mono font-semibold text-blue-600 dark:text-blue-400">
                    {item.symbol || '—'}
                  </td>
                  <td className="px-4 py-3 hidden sm:table-cell text-neutral-700 dark:text-neutral-300">
                    {item.company_name || '—'}
                  </td>
                  <td className="px-4 py-3 hidden md:table-cell text-neutral-500 dark:text-neutral-400 max-w-[200px] truncate">
                    {item.notes || <span className="italic text-neutral-300 dark:text-neutral-600">—</span>}
                  </td>
                  <td className="px-4 py-3 hidden md:table-cell text-neutral-400 text-xs">
                    {item.added_at ? new Date(item.added_at).toLocaleDateString() : '—'}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        if (item.symbol) removeMutation.mutate(item.symbol);
                      }}
                      className="p-1.5 rounded text-neutral-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
                      title="Remove from watchlist"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

export default WatchlistPage;
