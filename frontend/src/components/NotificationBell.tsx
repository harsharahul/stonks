/**
 * Notification bell — clean, modern replacement for the floating Live Alerts
 * overlay. Lives in the nav bar: a bell icon with an unread badge and a tiny
 * connection-status dot; clicking opens a dropdown listing recent alerts.
 * Keeps the same WebSocket wiring (useAlertsWebSocket) and REST hydration.
 */
import React, { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { Bell, CheckCheck, WifiOff } from 'lucide-react';

import apiClient from '../api/client';
import { useAlertsWebSocket, WebSocketMessage } from '../hooks/useWebSocket';
import { cn, formatRelativeTime } from '../utils/format';

interface AlertItem {
  id: string;
  ticker: string;
  alert_type: string;
  severity: string;
  title: string;
  message: string;
  triggered_at: string;
  acknowledged_at?: string;
  metadata?: any;
}

const MAX_ALERTS = 20;

const severityDot: Record<string, string> = {
  critical: 'bg-red-500',
  high: 'bg-red-400',
  medium: 'bg-amber-400',
  low: 'bg-neutral-400',
};

const NotificationBell: React.FC = () => {
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [open, setOpen] = useState(false);
  const panelRef = useRef<HTMLDivElement | null>(null);
  const buttonRef = useRef<HTMLButtonElement | null>(null);

  const { isConnected } = useAlertsWebSocket(undefined, {
    onMessage: (message: WebSocketMessage) => {
      if (message.type === 'alert') {
        const newAlert = message.data as AlertItem;
        setAlerts(prev => [newAlert, ...prev].slice(0, MAX_ALERTS));
        if (!newAlert.acknowledged_at) setUnreadCount(c => c + 1);
      }
    },
  });

  // Hydrate with recent alerts once
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await apiClient.get('/signals/alerts?hours=24&limit=20');
        if (!cancelled && res.data?.alerts) setAlerts(res.data.alerts.slice(0, MAX_ALERTS));
      } catch {
        /* alerts are non-critical chrome — stay silent */
      }
    })();
    return () => { cancelled = true; };
  }, []);

  // Close on outside click / Escape
  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      if (
        panelRef.current && !panelRef.current.contains(e.target as Node) &&
        buttonRef.current && !buttonRef.current.contains(e.target as Node)
      ) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false); };
    document.addEventListener('mousedown', onClick);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onClick);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  const toggle = () => {
    setOpen(o => !o);
    if (!open) setUnreadCount(0); // opening marks as seen
  };

  const clearAll = () => {
    setAlerts([]);
    setUnreadCount(0);
  };

  return (
    <div className="relative">
      <button
        ref={buttonRef}
        onClick={toggle}
        aria-label={`Notifications${unreadCount ? ` (${unreadCount} unread)` : ''}`}
        className={cn(
          'relative p-2 rounded-md transition-colors',
          'text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-white',
          'hover:bg-neutral-100 dark:hover:bg-neutral-800',
          open && 'bg-neutral-100 dark:bg-neutral-800',
        )}
      >
        <Bell className="w-5 h-5" />
        {/* connection status dot */}
        <span
          className={cn(
            'absolute bottom-1.5 right-1.5 w-1.5 h-1.5 rounded-full',
            isConnected ? 'bg-emerald-500' : 'bg-neutral-400',
          )}
          title={isConnected ? 'Live alerts connected' : 'Alerts disconnected'}
        />
        {/* unread badge */}
        {unreadCount > 0 && (
          <span className="absolute -top-0.5 -right-0.5 min-w-[16px] h-4 px-1 rounded-full bg-red-600 text-white text-[10px] font-bold flex items-center justify-center">
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div
          ref={panelRef}
          className="absolute right-0 mt-2 w-80 sm:w-96 rounded-xl border border-neutral-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 shadow-xl z-[70] overflow-hidden"
        >
          <div className="flex items-center justify-between px-4 py-2.5 border-b border-neutral-200 dark:border-neutral-800">
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-semibold">Notifications</h3>
              {!isConnected && (
                <span className="inline-flex items-center gap-1 text-[10px] text-neutral-400">
                  <WifiOff className="w-3 h-3" /> offline
                </span>
              )}
            </div>
            {alerts.length > 0 && (
              <button
                onClick={clearAll}
                className="inline-flex items-center gap-1 text-[11px] text-neutral-500 hover:text-neutral-800 dark:hover:text-neutral-200"
              >
                <CheckCheck className="w-3.5 h-3.5" /> clear
              </button>
            )}
          </div>

          <div className="max-h-96 overflow-y-auto">
            {alerts.length === 0 ? (
              <div className="px-4 py-10 text-center">
                <Bell className="w-6 h-6 mx-auto text-neutral-300 dark:text-neutral-600 mb-2" />
                <p className="text-sm text-neutral-500">No alerts right now.</p>
                <p className="text-xs text-neutral-400 mt-0.5">Market signals will land here.</p>
              </div>
            ) : (
              alerts.map(a => (
                <Link
                  key={a.id}
                  to={`/stocks/${a.ticker}`}
                  onClick={() => setOpen(false)}
                  className="flex items-start gap-3 px-4 py-3 border-b border-neutral-100 dark:border-neutral-800/60 hover:bg-neutral-50 dark:hover:bg-neutral-800/50 transition-colors"
                >
                  <span className={cn('mt-1.5 w-2 h-2 rounded-full flex-shrink-0', severityDot[a.severity] || 'bg-neutral-400')} />
                  <div className="min-w-0">
                    <div className="flex items-baseline gap-2">
                      <span className="font-mono text-xs font-bold">{a.ticker}</span>
                      <span className="text-[10px] uppercase tracking-wider text-neutral-400">{a.alert_type?.replace(/_/g, ' ')}</span>
                    </div>
                    <p className="text-sm text-neutral-700 dark:text-neutral-300 truncate">{a.title || a.message}</p>
                    <p className="text-[11px] text-neutral-400 mt-0.5">{a.triggered_at ? formatRelativeTime(a.triggered_at) : ''}</p>
                  </div>
                </Link>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default NotificationBell;
