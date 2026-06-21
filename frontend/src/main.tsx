import React from 'react';
import ReactDOM from 'react-dom/client';
import { App as AntdApp, ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import App from './App';
import { ThemeProvider, buildAntdTheme, useThemeMode } from './theme';
import './styles/index.css';

function ThemedApp() {
  const { mode } = useThemeMode();
  return (
    <ConfigProvider locale={zhCN} theme={buildAntdTheme(mode)}>
      <AntdApp>
        <App />
      </AntdApp>
    </ConfigProvider>
  );
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ThemeProvider>
      <ThemedApp />
    </ThemeProvider>
  </React.StrictMode>,
);
