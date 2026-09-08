import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Link, useLocation, useNavigate, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import StockDetail from './components/StockDetail';
import NotificationBell from './components/NotificationBell';
import MarketIntelligence from './components/MarketIntelligence';
import EnhancedStocksList from './components/EnhancedStocksList';
import WSBTrendingDashboard from './components/WSBTrendingDashboard';
import Dashboard from './components/Dashboard';
import AnomalyExplorer from './components/AnomalyExplorer';
import SignalsExplorer from './components/SignalsExplorer';
import CommandPalette from './components/CommandPalette';
import KeyboardShortcutsHelp from './components/KeyboardShortcutsHelp';
import StatusBar from './components/StatusBar';
import { useKeyboardShortcuts } from './hooks/useKeyboardShortcuts';
import SystemStatus from './components/SystemStatus';
import AdminDashboard from './components/AdminDashboard';
import WatchlistPage from './components/WatchlistPage';
import ProfilePage from './components/ProfilePage';
import UserMenu from './components/UserMenu';
import AITradingDesk from './components/AITradingDesk';
import PortfolioPage from './components/broker/PortfolioPage';
import StrategiesPage from './components/strategies/StrategiesPage';
import StrategyDetailPage from './components/strategies/StrategyDetailPage';
import { AuthProvider } from './auth/AuthProvider';
import { useAuth } from './hooks/useAuth';
import { TrendingUp, Brain, Menu, X, Search, Shield, Briefcase, Users, ChevronDown } from 'lucide-react';
import { cn } from './utils/format';

// Create a client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 5 * 60 * 1000, // 5 minutes
    },
  },
});

/** Route guard: redirect to / if user is not authenticated. */
const RequireAuth: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated, isLoading, isOidcEnabled } = useAuth();
  if (!isOidcEnabled) return <>{children}</>; // OIDC not configured: allow through
  if (isLoading) return null; // wait for OIDC to resolve
  if (!isAuthenticated) return <Navigate to="/" replace />;
  return <>{children}</>;
};

/** Route guard: require admin role. */
const RequireAdmin: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated, isAdmin, isLoading, isOidcEnabled } = useAuth();
  if (!isOidcEnabled) return <>{children}</>; // OIDC not configured: allow through
  if (isLoading) return null;
  if (!isAuthenticated) return <Navigate to="/" replace />;
  if (!isAdmin) return (
    <div className="max-w-md mx-auto mt-20 text-center">
      <Shield className="w-12 h-12 mx-auto text-neutral-300 dark:text-neutral-600 mb-4" />
      <h2 className="text-xl font-semibold text-neutral-800 dark:text-white mb-2">Admin Only</h2>
      <p className="text-neutral-500 dark:text-neutral-400">You don't have permission to access this page.</p>
    </div>
  );
  return <>{children}</>;
};

/** OIDC callback: handles the redirect from Authentik. */
const OidcCallback: React.FC = () => {
  const { isLoading, isAuthenticated } = useAuth();
  if (isLoading) return <div className="flex items-center justify-center h-screen text-neutral-500">Completing sign-in...</div>;
  if (isAuthenticated) return <Navigate to="/" replace />;
  return <Navigate to="/" replace />;
};

// Grouped navigation: mirrors the platform architecture: market data,
// the unified intelligence brain, the social layer, personal trading.
interface NavLeaf { to: string; label: string; description: string }
interface NavGroup { label: string; icon: React.ReactNode; match: (p: string) => boolean; children: NavLeaf[] }

const NAV_ACTIVE = 'bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300';
const NAV_IDLE = 'text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-white hover:bg-neutral-100 dark:hover:bg-neutral-800';

const NavDropdown: React.FC<{ group: NavGroup; pathname: string }> = ({ group, pathname }) => {
  const [open, setOpen] = useState(false);
  const ref = React.useRef<HTMLDivElement>(null);
  const active = group.match(pathname);

  useEffect(() => { setOpen(false); }, [pathname]);
  useEffect(() => {
    const onClick = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); };
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false); };
    document.addEventListener('mousedown', onClick);
    document.addEventListener('keydown', onKey);
    return () => { document.removeEventListener('mousedown', onClick); document.removeEventListener('keydown', onKey); };
  }, []);

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(v => !v)}
        className={cn('flex items-center gap-1 px-3 py-2 rounded-md text-sm font-medium transition-colors', active ? NAV_ACTIVE : NAV_IDLE)}
      >
        {group.icon}
        {group.label}
        <ChevronDown className={cn('w-3.5 h-3.5 transition-transform', open && 'rotate-180')} />
      </button>
      {open && (
        <div className="absolute left-0 top-full mt-1 w-64 bg-white dark:bg-neutral-800 border border-neutral-200 dark:border-neutral-700 rounded-lg shadow-lg p-1.5 z-50">
          {group.children.map(child => {
            const childActive = pathname === child.to || (child.to !== '/' && pathname.startsWith(child.to));
            return (
              <Link
                key={child.to}
                to={child.to}
                onClick={() => setOpen(false)}
                className={cn(
                  'block px-3 py-2 rounded-md transition-colors',
                  childActive ? 'bg-blue-50 dark:bg-blue-900/30' : 'hover:bg-neutral-50 dark:hover:bg-neutral-700/60'
                )}
              >
                <span className={cn('block text-sm font-medium', childActive ? 'text-blue-700 dark:text-blue-300' : 'text-neutral-800 dark:text-neutral-200')}>
                  {child.label}
                </span>
                <span className="block text-[11px] text-neutral-400 dark:text-neutral-500">{child.description}</span>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
};

const Navigation: React.FC<{ onOpenSearch: () => void }> = ({ onOpenSearch }) => {
  const location = useLocation();
  const { isAuthenticated, isAdmin, isOidcEnabled } = useAuth();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  useEffect(() => {
    setMobileMenuOpen(false);
  }, [location.pathname]);

  const flatLinks = [
    { to: '/', label: 'Dashboard', match: (p: string) => p === '/' },
    { to: '/stocks', label: 'Stocks', match: (p: string) => p.startsWith('/stocks') },
  ];

  const groups: NavGroup[] = [
    {
      label: 'Intelligence',
      icon: <Brain className="w-4 h-4" />,
      match: p => ['/desk', '/intelligence', '/signals', '/anomalies'].some(x => p.startsWith(x)),
      children: [
        { to: '/desk', label: 'AI Desk', description: '12-agent debate verdicts' },
        { to: '/intelligence', label: 'Market Intelligence', description: 'Briefs, outlook, recommendations' },
        { to: '/signals', label: 'Signals', description: 'All sources, verified win rates' },
        { to: '/anomalies', label: 'Anomalies', description: 'Statistical outliers' },
      ],
    },
    {
      label: 'Social',
      icon: <Users className="w-4 h-4" />,
      match: p => p.startsWith('/strategies') || p === '/wsb-trending',
      children: [
        { to: '/strategies', label: 'Strategies', description: 'Follow verified track records' },
        { to: '/wsb-trending', label: 'WSB Trending', description: 'Retail buzz radar' },
      ],
    },
    ...(isAuthenticated ? [{
      label: 'Trading',
      icon: <Briefcase className="w-4 h-4" />,
      match: (p: string) => p === '/portfolio' || p === '/watchlist',
      children: [
        { to: '/portfolio', label: 'Portfolio', description: 'Positions & orders via Alpaca' },
        { to: '/watchlist', label: 'Watchlist', description: 'Starred tickers' },
      ],
    }] : []),
  ];

  // Without OIDC (bare dev) the user menu is hidden, so System/Admin need a home here.
  const devOnlyLinks = !isOidcEnabled
    ? [
        { to: '/system', label: 'System', match: (p: string) => p === '/system' },
        { to: '/admin', label: 'Admin', match: (p: string) => p === '/admin' },
      ]
    : [];

  return (
    <nav className="bg-white dark:bg-neutral-900 border-b border-neutral-200 dark:border-neutral-700 relative z-50">
      <div className="max-w-7xl mx-auto px-4">
        <div className="flex justify-between h-16">
          <div className="flex items-center">
            <Link to="/" className="flex items-center" aria-label="Stonks home">
              <img src="/brand/stonks-logo.svg" alt="" className="h-7 w-auto dark:hidden" />
              <img src="/brand/stonks-logo-dark.svg" alt="" className="h-7 w-auto hidden dark:block" />
              <h1 className="sr-only">Stonks</h1>
            </Link>
          </div>
          {/* Desktop nav */}
          <div className="hidden md:flex items-center space-x-1">
            {flatLinks.map((link) => (
              <Link
                key={link.to}
                to={link.to}
                className={cn(
                  'px-3 py-2 rounded-md text-sm font-medium transition-colors',
                  link.match(location.pathname) ? NAV_ACTIVE : NAV_IDLE
                )}
              >
                {link.label}
              </Link>
            ))}
            {groups.map((group) => (
              <NavDropdown key={group.label} group={group} pathname={location.pathname} />
            ))}
            {devOnlyLinks.map((link) => (
              <Link
                key={link.to}
                to={link.to}
                className={cn(
                  'px-3 py-2 rounded-md text-sm font-medium transition-colors',
                  link.match(location.pathname) ? NAV_ACTIVE : NAV_IDLE
                )}
              >
                {link.label}
              </Link>
            ))}
            {/* Search trigger */}
            <button
              onClick={onOpenSearch}
              className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-neutral-200 dark:border-neutral-700 text-sm text-neutral-500 dark:text-neutral-400 hover:text-neutral-700 dark:hover:text-neutral-200 hover:border-neutral-300 dark:hover:border-neutral-600 hover:bg-neutral-50 dark:hover:bg-neutral-800 transition-colors ml-2"
            >
              <Search className="w-3.5 h-3.5" />
              <span className="hidden lg:inline">Search</span>
              <kbd className="hidden lg:inline text-[10px] font-mono bg-neutral-100 dark:bg-neutral-700 text-neutral-400 dark:text-neutral-400 px-1 py-0.5 rounded border border-neutral-200 dark:border-neutral-600">
                Ctrl+K
              </kbd>
            </button>
            {/* Notifications */}
            <div className="ml-1">
              <NotificationBell />
            </div>
            {/* User menu */}
            <div className="ml-1">
              <UserMenu />
            </div>
          </div>
          {/* Mobile: search + notifications + user + hamburger */}
          <div className="md:hidden flex items-center gap-1">
            <button
              className="flex items-center p-2 rounded-md text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-white hover:bg-neutral-100 dark:hover:bg-neutral-800"
              onClick={onOpenSearch}
              aria-label="Search"
            >
              <Search className="w-5 h-5" />
            </button>
            <NotificationBell />
            <UserMenu />
            <button
              className="flex items-center p-2 rounded-md text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-white hover:bg-neutral-100 dark:hover:bg-neutral-800"
              onClick={() => setMobileMenuOpen((v) => !v)}
              aria-label="Toggle menu"
            >
              {mobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
            </button>
          </div>
        </div>
      </div>
      {/* Mobile slide-down menu */}
      <div
        className={cn(
          'md:hidden overflow-hidden transition-all duration-200 ease-in-out border-t border-neutral-200 dark:border-neutral-700',
          mobileMenuOpen ? 'max-h-[34rem] overflow-y-auto' : 'max-h-0 border-t-0'
        )}
      >
        <div className="px-2 py-2 space-y-1 bg-white dark:bg-neutral-900">
          {flatLinks.concat(devOnlyLinks).map((link) => (
            <Link
              key={link.to}
              to={link.to}
              className={cn(
                'block py-2.5 px-4 rounded-md text-base font-medium transition-colors',
                link.match(location.pathname) ? NAV_ACTIVE : NAV_IDLE
              )}
            >
              {link.label}
            </Link>
          ))}
          {groups.map((group) => (
            <div key={group.label}>
              <div className="px-4 pt-3 pb-1 text-[10px] font-semibold uppercase tracking-wider text-neutral-400 dark:text-neutral-500">
                {group.label}
              </div>
              {group.children.map((child) => (
                <Link
                  key={child.to}
                  to={child.to}
                  className={cn(
                    'block py-2.5 px-4 rounded-md text-base font-medium transition-colors',
                    (location.pathname === child.to || (child.to !== '/' && location.pathname.startsWith(child.to))) ? NAV_ACTIVE : NAV_IDLE
                  )}
                >
                  {child.label}
                </Link>
              ))}
            </div>
          ))}
        </div>
      </div>
    </nav>
  );
};

const AppContent: React.FC = () => {
  const navigate = useNavigate();
  const [commandPaletteOpen, setCommandPaletteOpen] = useState(false);
  const [shortcutsHelpOpen, setShortcutsHelpOpen] = useState(false);

  useKeyboardShortcuts([
    { key: 'k', ctrl: true, handler: () => setCommandPaletteOpen(true), description: 'Open search', category: 'Search' },
    { key: '/', handler: () => setCommandPaletteOpen(true), description: 'Quick stock search', category: 'Search' },
    { key: '?', handler: () => setShortcutsHelpOpen(true), description: 'Keyboard shortcuts', category: 'Actions' },
    { key: '1', ctrl: true, handler: () => navigate('/'), description: 'Dashboard', category: 'Navigation' },
    { key: '2', ctrl: true, handler: () => navigate('/stocks'), description: 'Stocks', category: 'Navigation' },
    { key: '3', ctrl: true, handler: () => navigate('/intelligence'), description: 'AI Intelligence', category: 'Navigation' },
    { key: '4', ctrl: true, handler: () => navigate('/signals'), description: 'Signals', category: 'Navigation' },
    { key: '5', ctrl: true, handler: () => navigate('/anomalies'), description: 'Anomalies', category: 'Navigation' },
    { key: '6', ctrl: true, handler: () => navigate('/wsb-trending'), description: 'WSB Trending', category: 'Navigation' },
    { key: '7', ctrl: true, handler: () => navigate('/system'), description: 'System Status', category: 'Navigation' },
    { key: '8', ctrl: true, handler: () => navigate('/admin'), description: 'Admin Dashboard', category: 'Navigation' },
  ]);

  return (
    <div className="min-h-screen bg-neutral-50 dark:bg-neutral-900 md:pb-8">
      <Navigation onOpenSearch={() => setCommandPaletteOpen(true)} />
      <Routes>
        {/* Public routes */}
        <Route path="/" element={<Dashboard />} />
        <Route path="/stocks" element={<EnhancedStocksList />} />
        <Route path="/stocks/:symbol" element={<StockDetail />} />
        <Route path="/desk" element={<AITradingDesk />} />
        <Route path="/desk/:ticker" element={<AITradingDesk />} />
        <Route path="/intelligence" element={<MarketIntelligence />} />
        <Route path="/signals" element={<SignalsExplorer />} />
        <Route path="/strategies" element={<StrategiesPage />} />
        <Route path="/strategies/:slug" element={<StrategyDetailPage />} />
        <Route path="/anomalies" element={<AnomalyExplorer />} />
        <Route path="/wsb-trending" element={<WSBTrendingDashboard />} />
        <Route path="/system" element={<SystemStatus />} />

        {/* OIDC callback */}
        <Route path="/callback" element={<OidcCallback />} />

        {/* Authenticated routes */}
        <Route path="/portfolio" element={<RequireAuth><PortfolioPage /></RequireAuth>} />
        <Route path="/watchlist" element={<RequireAuth><WatchlistPage /></RequireAuth>} />
        <Route path="/profile" element={<RequireAuth><ProfilePage /></RequireAuth>} />

        {/* Admin route */}
        <Route path="/admin" element={<RequireAdmin><AdminDashboard /></RequireAdmin>} />
      </Routes>

      {/* Command palette & keyboard shortcuts */}
      <CommandPalette
        open={commandPaletteOpen}
        onOpenChange={setCommandPaletteOpen}
        onShowShortcuts={() => { setCommandPaletteOpen(false); setShortcutsHelpOpen(true); }}
      />
      <KeyboardShortcutsHelp open={shortcutsHelpOpen} onOpenChange={setShortcutsHelpOpen} />
      <StatusBar />
    </div>
  );
};

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Router>
        <AuthProvider>
          <AppContent />
        </AuthProvider>
      </Router>
    </QueryClientProvider>
  );
}

export default App;
