import { useEffect, useState } from 'react';
import { api } from '@/api/client';
import Studio from '@/pages/Studio';
import ConfigCenter from '@/pages/ConfigCenter';
import History from '@/pages/History';
import Secrets from '@/pages/Secrets';
import type { ModuleName } from '@/types';

type TopTab = 'studio' | 'configs' | 'history' | 'secrets';
type StudioMode = `studio-${ModuleName}`;
type Tab = TopTab | StudioMode;

const STUDIO_CHILDREN: { id: ModuleName; label: string; emoji: string; tagline: string }[] = [
  { id: 'image', label: 'Image',  emoji: '🖼', tagline: 'Text → Image' },
  { id: 'voice', label: 'Voice',  emoji: '🔊', tagline: 'Text → Speech' },
  { id: 'music', label: 'Music',  emoji: '🎵', tagline: 'Text → Music' },
  { id: 'video', label: 'Video',  emoji: '🎬', tagline: 'Text/Image → Video' },
];

function isStudio(t: Tab): t is StudioMode {
  return typeof t === 'string' && t.startsWith('studio-');
}

function studioModule(t: Tab): ModuleName {
  return (t as StudioMode).replace('studio-', '') as ModuleName;
}

export default function App() {
  const [tab, setTab] = useState<Tab>(() => (localStorage.getItem('tab') as Tab) || 'studio-image');
  const [health, setHealth] = useState<{ ok: boolean; message: string }>({ ok: false, message: '...' });

  useEffect(() => {
    api.health().then((h) => setHealth({ ok: h.status === 'ok' && h.db, message: h.db ? `v${h.version ?? '?'}` : 'DB error' }))
      .catch((e) => setHealth({ ok: false, message: String(e?.message ?? e) }));
  }, []);

  useEffect(() => { localStorage.setItem('tab', tab); }, [tab]);

  // High-level "section": Studio is highlighted when any studio-* tab is active.
  const studioActive = isStudio(tab);

  return (
    <div className="app">
      <aside className="sidebar">
        <h1><span className="dot" />MiniMax Tool</h1>

        {/* Top-level Studio parent + 4 sub-items */}
        <div
          className={'nav-item nav-parent' + (studioActive ? ' active' : '')}
          onClick={() => setTab('studio-image')}
        >
          <span className="icon">▶</span> Studio
        </div>
        {STUDIO_CHILDREN.map((c) => {
          const id = `studio-${c.id}` as StudioMode;
          return (
            <div
              key={c.id}
              className={'nav-item nav-child' + (tab === id ? ' active' : '')}
              onClick={() => setTab(id)}
              title={c.tagline}
            >
              <span className="icon">{c.emoji}</span> {c.label}
            </div>
          );
        })}

        <div className="nav-sep" />

        <div className={'nav-item' + (tab === 'configs' ? ' active' : '')} onClick={() => setTab('configs')}>
          <span className="icon">⚙</span> Config Center
        </div>
        <div className={'nav-item' + (tab === 'history' ? ' active' : '')} onClick={() => setTab('history')}>
          <span className="icon">⌛</span> History
        </div>
        <div className={'nav-item' + (tab === 'secrets' ? ' active' : '')} onClick={() => setTab('secrets')}>
          <span className="icon">🔑</span> Secrets
        </div>

        <div className="footer">
          <div>API: <span className={health.ok ? 'tag success' : 'tag failed'}>{health.message}</span></div>
          <div style={{ marginTop: 4 }}>Port 9060</div>
        </div>
      </aside>
      <main className="main">
        {isStudio(tab) && <Studio module={studioModule(tab)} />}
        {tab === 'configs' && <ConfigCenter />}
        {tab === 'history' && <History />}
        {tab === 'secrets' && <Secrets />}
      </main>
    </div>
  );
}
