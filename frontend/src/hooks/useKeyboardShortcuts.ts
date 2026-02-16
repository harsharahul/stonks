import { useEffect, useCallback, useRef } from 'react';

export interface Shortcut {
  key: string;
  ctrl?: boolean;
  shift?: boolean;
  description: string;
  category: 'Navigation' | 'Search' | 'Actions' | 'Tables';
  handler: () => void;
  /** Skip when focus is in an input/textarea (default: true) */
  ignoreWhenEditing?: boolean;
}

const isEditableTarget = (target: EventTarget | null): boolean => {
  if (!target || !(target instanceof HTMLElement)) return false;
  const tag = target.tagName.toLowerCase();
  if (tag === 'input' || tag === 'textarea' || tag === 'select') return true;
  if (target.isContentEditable) return true;
  // cmdk input has role="combobox"
  if (target.getAttribute('role') === 'combobox') return true;
  return false;
};

export const useKeyboardShortcuts = (shortcuts: Shortcut[]) => {
  const shortcutsRef = useRef(shortcuts);
  shortcutsRef.current = shortcuts;

  const handler = useCallback((e: KeyboardEvent) => {
    for (const shortcut of shortcutsRef.current) {
      const wantCtrl = shortcut.ctrl ?? false;
      const wantShift = shortcut.shift ?? false;
      const ignoreEditing = shortcut.ignoreWhenEditing ?? true;

      // Match modifier keys
      const ctrlMatch = wantCtrl ? (e.ctrlKey || e.metaKey) : !(e.ctrlKey || e.metaKey);
      const shiftMatch = wantShift ? e.shiftKey : !e.shiftKey;

      if (!ctrlMatch || !shiftMatch) continue;

      // Match the key
      const keyMatch =
        e.key === shortcut.key ||
        e.key.toLowerCase() === shortcut.key.toLowerCase();

      if (!keyMatch) continue;

      // Skip if editing and shortcut doesn't want editing context
      if (ignoreEditing && !wantCtrl && isEditableTarget(e.target)) continue;

      e.preventDefault();
      e.stopPropagation();
      shortcut.handler();
      return;
    }
  }, []);

  useEffect(() => {
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [handler]);
};
