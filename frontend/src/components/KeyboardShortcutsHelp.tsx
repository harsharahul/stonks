import React, { useEffect } from 'react';
import { X, Keyboard } from 'lucide-react';

interface KeyboardShortcutsHelpProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const Kbd: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <kbd className="inline-flex items-center justify-center min-w-[24px] px-1.5 py-0.5 bg-neutral-100 dark:bg-neutral-700
                  text-neutral-700 dark:text-neutral-300 font-mono text-xs rounded border border-neutral-200 dark:border-neutral-600">
    {children}
  </kbd>
);

interface ShortcutRowProps {
  keys: React.ReactNode;
  label: string;
}

const ShortcutRow: React.FC<ShortcutRowProps> = ({ keys, label }) => (
  <div className="flex items-center justify-between py-1.5">
    <div className="flex items-center gap-1">{keys}</div>
    <span className="text-sm text-neutral-600 dark:text-neutral-300">{label}</span>
  </div>
);

const sections = [
  {
    title: 'Search',
    shortcuts: [
      { keys: <><Kbd>Ctrl</Kbd><span className="text-neutral-400 dark:text-neutral-500">+</span><Kbd>K</Kbd></>, label: 'Open search' },
      { keys: <Kbd>/</Kbd>, label: 'Quick stock search' },
    ],
  },
  {
    title: 'Navigation',
    shortcuts: [
      { keys: <><Kbd>Ctrl</Kbd><span className="text-neutral-400 dark:text-neutral-500">+</span><Kbd>1</Kbd></>, label: 'Dashboard' },
      { keys: <><Kbd>Ctrl</Kbd><span className="text-neutral-400 dark:text-neutral-500">+</span><Kbd>2</Kbd></>, label: 'Stocks' },
      { keys: <><Kbd>Ctrl</Kbd><span className="text-neutral-400 dark:text-neutral-500">+</span><Kbd>3</Kbd></>, label: 'AI Intelligence' },
      { keys: <><Kbd>Ctrl</Kbd><span className="text-neutral-400 dark:text-neutral-500">+</span><Kbd>4</Kbd></>, label: 'Signals' },
      { keys: <><Kbd>Ctrl</Kbd><span className="text-neutral-400 dark:text-neutral-500">+</span><Kbd>5</Kbd></>, label: 'Anomalies' },
      { keys: <><Kbd>Ctrl</Kbd><span className="text-neutral-400 dark:text-neutral-500">+</span><Kbd>6</Kbd></>, label: 'WSB Trending' },
      { keys: <><Kbd>Ctrl</Kbd><span className="text-neutral-400 dark:text-neutral-500">+</span><Kbd>7</Kbd></>, label: 'System Status' },
      { keys: <><Kbd>Ctrl</Kbd><span className="text-neutral-400 dark:text-neutral-500">+</span><Kbd>8</Kbd></>, label: 'Admin Dashboard' },
      { keys: <Kbd>Esc</Kbd>, label: 'Close modal' },
    ],
  },
  {
    title: 'Actions',
    shortcuts: [
      { keys: <Kbd>?</Kbd>, label: 'This help' },
    ],
  },
];

const KeyboardShortcutsHelp: React.FC<KeyboardShortcutsHelpProps> = ({ open, onOpenChange }) => {
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        onOpenChange(false);
      }
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [open, onOpenChange]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[100]" onClick={() => onOpenChange(false)}>
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" />
      {/* Modal */}
      <div
        className="fixed top-[15%] left-1/2 -translate-x-1/2 w-full max-w-md bg-white dark:bg-neutral-800 rounded-xl shadow-2xl p-6"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Keyboard className="w-5 h-5 text-neutral-700 dark:text-neutral-300" />
            <h2 className="text-lg font-bold text-neutral-900 dark:text-white">Keyboard Shortcuts</h2>
          </div>
          <button
            onClick={() => onOpenChange(false)}
            className="p-1 rounded-md hover:bg-neutral-100 dark:hover:bg-neutral-700 text-neutral-500 dark:text-neutral-400 hover:text-neutral-700 dark:hover:text-neutral-300 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Sections */}
        {sections.map((section) => (
          <div key={section.title}>
            <h3 className="text-xs font-semibold text-neutral-500 dark:text-neutral-400 uppercase tracking-wider mt-4 mb-2">
              {section.title}
            </h3>
            <div className="space-y-0">
              {section.shortcuts.map((shortcut, i) => (
                <ShortcutRow key={i} keys={shortcut.keys} label={shortcut.label} />
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default KeyboardShortcutsHelp;
