import { useEffect, useState } from 'react';
import { Layout, Menu, Button, Tooltip, Tag, theme as antdTheme } from 'antd';
import type { MenuProps } from 'antd';
import {
  ExperimentOutlined,
  BulbOutlined,
  BulbFilled,
  ApiOutlined,
  HistoryOutlined,
  KeyOutlined,
  TranslationOutlined,
} from '@ant-design/icons';
import { api } from '@/api/client';
import type { ModuleName } from '@/types';
import Studio from '@/pages/Studio';
import ConfigCenter from '@/pages/ConfigCenter';
import History from '@/pages/History';
import Secrets from '@/pages/Secrets';
import Translate from '@/pages/Translate';
import { useThemeMode } from '@/theme';

const { Sider, Header, Content } = Layout;

type StudioMode = `studio-${ModuleName}`;
type Tab = 'translate' | StudioMode | 'configs' | 'history' | 'secrets';

const STUDIO_CHILDREN: {
  id: ModuleName;
  label: string;
  emoji: string;
  tagline: string;
  icon: React.ReactNode;
}[] = [
  { id: 'image', label: 'Image', emoji: '🖼', tagline: 'Text → Image', icon: <ExperimentOutlined /> },
  { id: 'voice', label: 'Voice', emoji: '🔊', tagline: 'Text → Speech', icon: <ExperimentOutlined /> },
  { id: 'music', label: 'Music', emoji: '🎵', tagline: 'Text → Music',  icon: <ExperimentOutlined /> },
  { id: 'video', label: 'Video', emoji: '🎬', tagline: 'Text/Image → Video', icon: <ExperimentOutlined /> },
];

function isStudio(t: Tab): t is StudioMode {
  return typeof t === 'string' && t.startsWith('studio-');
}

function studioModule(t: Tab): ModuleName {
  return (t as StudioMode).replace('studio-', '') as ModuleName;
}

function readTab(): Tab {
  const stored = localStorage.getItem('tab') as Tab | null;
  if (!stored) return 'translate';
  return stored;
}

export default function App() {
  const { mode, toggle } = useThemeMode();
  const { token } = antdTheme.useToken();
  const [tab, setTab] = useState<Tab>(readTab);
  const [collapsed, setCollapsed] = useState(false);
  const [health, setHealth] = useState<{ ok: boolean; message: string }>({ ok: false, message: '...' });

  useEffect(() => {
    api.health()
      .then((h) =>
        setHealth({ ok: h.status === 'ok' && h.db, message: h.db ? `v${h.version ?? '?'}` : 'DB error' }),
      )
      .catch((e) => setHealth({ ok: false, message: String(e?.message ?? e) }));
  }, []);

  useEffect(() => { localStorage.setItem('tab', tab); }, [tab]);

  const studioActive = isStudio(tab);

  const items: MenuProps['items'] = [
    {
      key: 'translate',
      icon: <TranslationOutlined />,
      label: 'Translate',
    },
    {
      key: 'studio-submenu',
      icon: <ExperimentOutlined />,
      label: 'Studio',
      type: 'submenu',
      children: STUDIO_CHILDREN.map((c) => ({
        key: `studio-${c.id}`,
        icon: c.icon,
        label: `${c.emoji} ${c.label}`,
        title: c.tagline,
      })),
    },
    { type: 'divider' },
    { key: 'configs', icon: <ApiOutlined />, label: 'Config Center' },
    { key: 'secrets', icon: <KeyOutlined />, label: 'Secrets' },
    { key: 'history', icon: <HistoryOutlined />, label: 'History' },
  ];

  // Highlight the Studio group when any studio-* tab is active.
  const selectedKeys: string[] = [tab as string];

  return (
    <Layout className="app-shell">
      <Sider
        width={232}
        collapsible
        collapsed={collapsed}
        onCollapse={setCollapsed}
        className="app-sider"
        style={{
          borderRight: `1px solid ${token.colorBorderSecondary}`,
          background: token.colorBgContainer,
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            padding: '20px 20px 16px',
            fontSize: 15,
            fontWeight: 600,
          }}
        >
          <span className="dot" />
          {collapsed ? <TranslationOutlined /> : 'MiniMax Tool'}
        </div>
        <Menu
          mode="inline"
          selectedKeys={selectedKeys}
          items={items}
          onClick={({ key }) => setTab(key as Tab)}
          style={{ borderInlineEnd: 0, background: 'transparent' }}
        />
        <div
          className={`sidebar-status${collapsed ? ' collapsed' : ''}`}
          style={{
            color: token.colorTextTertiary,
            borderTopColor: token.colorBorderSecondary,
            background: token.colorBgContainer,
          }}
          title={collapsed ? `API ${health.message} · Port 9060` : undefined}
        >
          {collapsed ? (
            <span className={`sidebar-health-dot ${health.ok ? 'ok' : 'error'}`} />
          ) : (
            <>
              <div className="sidebar-status-line">
                <span>API</span>
                <Tag color={health.ok ? 'success' : 'error'}>{health.message}</Tag>
              </div>
              <div className="sidebar-port">Port 9060</div>
            </>
          )}
        </div>
      </Sider>
      <Layout>
        <Header
          style={{
            background: token.colorBgContainer,
            borderBottom: `1px solid ${token.colorBorderSecondary}`,
            padding: 0,
          }}
        >
          <div className="app-header-inner">
            <div className="app-header-title">
              {tabTitle(tab)}
            </div>
            <Tooltip title={mode === 'dark' ? 'Switch to light' : 'Switch to dark'}>
              <Button
                shape="circle"
                icon={mode === 'dark' ? <BulbOutlined /> : <BulbFilled />}
                onClick={toggle}
                aria-label="toggle theme"
              />
            </Tooltip>
          </div>
        </Header>
        <Content className="app-content">
          {tab === 'translate' && <Translate />}
          {isStudio(tab) && <Studio module={studioModule(tab)} />}
          {tab === 'configs' && <ConfigCenter />}
          {tab === 'history' && <History />}
          {tab === 'secrets' && <Secrets />}
        </Content>
      </Layout>
    </Layout>
  );
}

function tabTitle(tab: Tab): React.ReactNode {
  if (tab === 'translate') return <>🌐 Translate</>;
  if (tab === 'configs') return <>⚙️ Config Center</>;
  if (tab === 'secrets') return <>🔑 Secrets</>;
  if (tab === 'history') return <>⌛ History</>;
  if (isStudio(tab)) {
    const c = STUDIO_CHILDREN.find((x) => `studio-${x.id}` === tab);
    return <>{c?.emoji} {c?.label} Studio</>;
  }
  return null;
}
