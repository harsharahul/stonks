import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Link, useLocation, useNavigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import StockDetail from './components/StockDetail';
import RealTimeAlerts from './components/RealTimeAlerts';
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
import { TrendingUp, Brain, AlertTriangle, Zap, Menu, X, Search } from 'lucide-react';
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

const navLinks = [
  { to: '/', label: 'Dashboard', match: (p: string) => p === '/', activeClass: 'bg-blue-100 text-blue-700' },
  { to: '/stocks', label: 'Stocks', match: (p: string) => p.startsWith('/stocks'), activeClass: 'bg-blue-100 text-blue-700' },
  { to: '/intelligence', label: 'AI Intelligence', icon: <Brain className="w-4 h-4 inline mr-1" />, match: (p: string) => p === '/intelligence', activeClass: 'bg-blue-100 text-blue-700' },
  { to: '/signals', label: 'Signals', icon: <Zap className="w-4 h-4 inline mr-1" />, match: (p: string) => p === '/signals', activeClass: 'bg-purple-100 text-purple-700' },
  { to: '/anomalies', label: 'Anomalies', icon: <AlertTriangle className="w-4 h-4 inline mr-1" />, match: (p: string) => p === '/anomalies', activeClass: 'bg-orange-100 text-orange-700' },
  { to: '/wsb-trending', label: '\u{1F412} WSB Trending', match: (p: string) => p === '/wsb-trending', activeClass: 'bg-red-100 text-red-700' },
];

const Navigation: React.FC<{ onOpenSearch: () => void }> = ({ onOpenSearch }) => {
  const location = useLocation();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  useEffect(() => {
    setMobileMenuOpen(false);
  }, [location.pathname]);

  return (
    <nav className="bg-white border-b border-neutral-200 relative z-50">
      <div className="max-w-7xl mx-auto px-4">
        <div className="flex justify-between h-16">
          <div className="flex items-center">
            <Link to="/" className="flex items-center space-x-2">
              <TrendingUp className="w-6 h-6 text-blue-600" />
              <h1 className="text-xl font-bold text-neutral-900">Stonks</h1>
            </Link>
          </div>
          {/* Desktop nav */}
          <div className="hidden md:flex items-center space-x-8">
            {navLinks.map((link) => (
              <Link
                key={link.to}
                to={link.to}
                className={cn(
                  'px-3 py-2 rounded-md text-sm font-medium transition-colors',
                  link.match(location.pathname)
                    ? link.activeClass
                    : 'text-neutral-600 hover:text-neutral-900 hover:bg-neutral-100'
                )}
              >
                {link.icon}{link.label}
              </Link>
            ))}
            {/* Search trigger */}
            <button
              onClick={onOpenSearch}
              className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-neutral-200 text-sm text-neutral-500 hover:text-neutral-700 hover:border-neutral-300 hover:bg-neutral-50 transition-colors"
            >
              <Search className="w-3.5 h-3.5" />
              <span>Search</span>
              <kbd className="text-[10px] font-mono bg-neutral-100 text-neutral-400 px-1 py-0.5 rounded border border-neutral-200">
                Ctrl+K
              </kbd>
            </button>
          </div>
          {/* Mobile: search + hamburger */}
          <div className="md:hidden flex items-center gap-1">
            <button
              className="flex items-center p-2 rounded-md text-neutral-600 hover:text-neutral-900 hover:bg-neutral-100"
              onClick={onOpenSearch}
              aria-label="Search"
            >
              <Search className="w-5 h-5" />
            </button>
            <button
              className="flex items-center p-2 rounded-md text-neutral-600 hover:text-neutral-900 hover:bg-neutral-100"
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
          'md:hidden overflow-hidden transition-all duration-200 ease-in-out border-t border-neutral-200',
          mobileMenuOpen ? 'max-h-80' : 'max-h-0 border-t-0'
        )}
      >
        <div className="px-2 py-2 space-y-1 bg-white">
          {navLinks.map((link) => (
            <Link
              key={link.to}
              to={link.to}
              className={cn(
                'block py-3 px-4 rounded-md text-base font-medium transition-colors',
                link.match(location.pathname)
                  ? link.activeClass
                  : 'text-neutral-600 hover:text-neutral-900 hover:bg-neutral-100'
              )}
            >
              {link.icon}{link.label}
            </Link>
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
  ]);

  return (
    <div className="min-h-screen bg-neutral-50 md:pb-8">
      <Navigation onOpenSearch={() => setCommandPaletteOpen(true)} />
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/stocks" element={<EnhancedStocksList />} />
        <Route path="/stocks/:symbol" element={<StockDetail />} />
        <Route path="/intelligence" element={<MarketIntelligence />} />
        <Route path="/signals" element={<SignalsExplorer />} />
        <Route path="/anomalies" element={<AnomalyExplorer />} />
        <Route path="/wsb-trending" element={<WSBTrendingDashboard />} />
      </Routes>

      {/* Real-time alerts overlay */}
      <RealTimeAlerts maxAlerts={15} autoAcknowledge={false} />

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
        <AppContent />
      </Router>
    </QueryClientProvider>
  );
}

export default App;
