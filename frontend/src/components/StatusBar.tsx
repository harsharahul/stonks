import React from 'react';

const Kbd: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <kbd className="bg-neutral-700 text-neutral-300 px-1.5 py-0.5 rounded text-[10px] font-mono border border-neutral-600">
    {children}
  </kbd>
);

const StatusBar: React.FC = () => (
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
        <Kbd>Ctrl+1-6</Kbd>
        <span>Navigate</span>
      </span>
    </div>
    <div className="ml-auto text-neutral-600">Stonks</div>
  </div>
);

export default StatusBar;
