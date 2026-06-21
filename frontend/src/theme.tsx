import { createContext, useContext, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { theme as antdTheme, type ThemeConfig } from 'antd';

type ThemeMode = 'light' | 'dark';

interface ThemeContextValue {
  mode: ThemeMode;
  toggle: () => void;
  setMode: (m: ThemeMode) => void;
}

const STORAGE_KEY = 'minimax.theme';

const ThemeContext = createContext<ThemeContextValue | null>(null);

function readInitialMode(): ThemeMode {
  if (typeof window === 'undefined') return 'dark';
  const stored = window.localStorage.getItem(STORAGE_KEY) as ThemeMode | null;
  if (stored === 'light' || stored === 'dark') return stored;
  // First visit: respect the OS preference, default to dark if unknown.
  const prefersLight = window.matchMedia?.('(prefers-color-scheme: light)').matches;
  return prefersLight ? 'light' : 'dark';
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<ThemeMode>(readInitialMode);

  useEffect(() => {
    window.localStorage.setItem(STORAGE_KEY, mode);
    // Helps the browser pick the right scrollbar / form chrome.
    document.documentElement.dataset.theme = mode;
    document.documentElement.style.colorScheme = mode;
  }, [mode]);

  const value = useMemo<ThemeContextValue>(
    () => ({
      mode,
      setMode,
      toggle: () => setMode((m) => (m === 'dark' ? 'light' : 'dark')),
    }),
    [mode],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useThemeMode(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error('useThemeMode must be used inside <ThemeProvider>');
  return ctx;
}

// ---------------------------------------------------------------------------
// antd ConfigProvider tokens
// ---------------------------------------------------------------------------

const SHARED_COMPONENTS: ThemeConfig['components'] = {
  Layout: {
    headerBg: 'transparent',
    headerHeight: 56,
    headerPadding: '0 24px',
    siderBg: 'transparent',
    bodyBg: 'transparent',
  },
  Menu: {
    itemBg: 'transparent',
    subMenuItemBg: 'transparent',
    itemHeight: 38,
    itemBorderRadius: 8,
    iconSize: 16,
  },
  Card: {
    borderRadiusLG: 12,
  },
};

export function buildAntdTheme(mode: ThemeMode): ThemeConfig {
  const isDark = mode === 'dark';
  return {
    algorithm: isDark ? antdTheme.darkAlgorithm : antdTheme.defaultAlgorithm,
    hashed: false,
    token: {
      colorPrimary: '#7c5cff',
      colorInfo: '#7c5cff',
      colorSuccess: '#4ade80',
      colorWarning: '#facc15',
      colorError: '#f87171',
      borderRadius: 8,
      fontFamily:
        "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', Roboto, sans-serif",
      fontSize: 14,
    },
    components: SHARED_COMPONENTS,
  };
}
