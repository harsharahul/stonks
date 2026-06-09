import React, { useState, useRef, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { LogOut, User, Star, Settings, ChevronDown } from 'lucide-react';
import { cn } from '../utils/format';

const UserMenu: React.FC = () => {
  const { isAuthenticated, isOidcEnabled, user, login, logout, isAdmin } = useAuth();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  // Close on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  // If OIDC is not configured, show nothing
  if (!isOidcEnabled) return null;

  // Not logged in → sign-in button
  if (!isAuthenticated || !user) {
    return (
      <button
        onClick={login}
        className="px-3 py-1.5 rounded-lg text-sm font-medium bg-blue-600 text-white hover:bg-blue-700 transition-colors"
      >
        Sign In
      </button>
    );
  }

  // Logged in → avatar dropdown
  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 px-2 py-1 rounded-lg hover:bg-neutral-100 dark:hover:bg-neutral-800 transition-colors"
      >
        {user.avatarUrl ? (
          <img src={user.avatarUrl} alt="" className="w-7 h-7 rounded-full" />
        ) : (
          <div className="w-7 h-7 rounded-full bg-blue-600 flex items-center justify-center text-white text-xs font-bold">
            {user.name.charAt(0).toUpperCase()}
          </div>
        )}
        <span className="hidden sm:inline text-sm text-neutral-700 dark:text-neutral-300 max-w-[120px] truncate">
          {user.name}
        </span>
        <ChevronDown className={cn('w-3.5 h-3.5 text-neutral-400 transition-transform', open && 'rotate-180')} />
      </button>

      {open && (
        <div className="absolute right-0 mt-1 w-56 bg-white dark:bg-neutral-800 border border-neutral-200 dark:border-neutral-700 rounded-lg shadow-lg py-1 z-50">
          <div className="px-3 py-2 border-b border-neutral-100 dark:border-neutral-700">
            <p className="text-sm font-medium text-neutral-900 dark:text-white truncate">{user.name}</p>
            <p className="text-xs text-neutral-500 dark:text-neutral-400 truncate">{user.email}</p>
            {isAdmin && (
              <span className="inline-block mt-1 px-1.5 py-0.5 text-[10px] font-semibold rounded bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300">
                ADMIN
              </span>
            )}
          </div>

          <Link
            to="/watchlist"
            onClick={() => setOpen(false)}
            className="flex items-center gap-2 px-3 py-2 text-sm text-neutral-700 dark:text-neutral-300 hover:bg-neutral-50 dark:hover:bg-neutral-700"
          >
            <Star className="w-4 h-4" /> My Watchlist
          </Link>

          <Link
            to="/profile"
            onClick={() => setOpen(false)}
            className="flex items-center gap-2 px-3 py-2 text-sm text-neutral-700 dark:text-neutral-300 hover:bg-neutral-50 dark:hover:bg-neutral-700"
          >
            <Settings className="w-4 h-4" /> Preferences
          </Link>

          <div className="border-t border-neutral-100 dark:border-neutral-700" />

          <button
            onClick={() => { setOpen(false); logout(); }}
            className="flex items-center gap-2 w-full px-3 py-2 text-sm text-red-600 dark:text-red-400 hover:bg-neutral-50 dark:hover:bg-neutral-700"
          >
            <LogOut className="w-4 h-4" /> Sign Out
          </button>
        </div>
      )}
    </div>
  );
};

export default UserMenu;
