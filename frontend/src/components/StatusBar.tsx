import React from 'react';
import { Sun, Moon, Monitor } from 'lucide-react';
import { useTheme, type Theme } from '../hooks/useTheme';

const Kbd: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <kbd className="bg-neutral-700 text-neutral-300 px-1.5 py-0.5 rounded text-[10px] font-mono border border-neutral-600">
    {children}
  </kbd>
);

const THEME_CYCLE: Theme[] = ['system', 'light', 'dark'];
const THEME_ICON: Record<Theme, React.ReactNode> = {
  system: <Monitor size={12} />,
  light: <Sun size={12} />,
  dark: <Moon size={12} />,
};
const THEME_LABEL: Record<Theme, string> = {
  system: 'System',
  light: 'Light',
  dark: 'Dark',
};

const StatusBar: React.FC = () => {
  const { theme, setTheme } = useTheme();

  const cycleTheme = () => {
    const idx = THEME_CYCLE.indexOf(theme);
    setTheme(THEME_CYCLE[(idx + 1) % THEME_CYCLE.length]);
  };

  return (
    <div className="fixed bottom-0 left-0 right-0 h-8 bg-neutral-800 text-neutral-400
                    text-xs font-mono hidden md:flex items-center px-4 z-40 border-t border-neutral-700">
      <div className="flex items-center gap-4">
        <span className="flex items-center gap-1.5">
          <Kbd>Ctrl+K</Kbd>
          <span>Search</span>
        </span>
        <span className="w-px h-3.5 bg-neutral-700" />
        <span className="flex items-center gap-1.5">
          <Kbd>?</Kbd>
          <span>Shortcuts</span>
        </span>
        <span className="w-px h-3.5 bg-neutral-700" />
        <span className="flex items-center gap-1.5">
          <Kbd>Ctrl+1-8</Kbd>
          <span>Navigate</span>
        </span>
      </div>
      <div className="ml-auto flex items-center gap-3">
        <button
          onClick={cycleTheme}
          className="flex items-center gap-1.5 hover:text-neutral-200 transition-colors"
          title={`Theme: ${THEME_LABEL[theme]}`}
        >
          {THEME_ICON[theme]}
          <span>{THEME_LABEL[theme]}</span>
        </button>
        <span className="text-neutral-600">Stonks</span>
      </div>
    </div>
  );
};

export default StatusBar;
