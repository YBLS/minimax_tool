import { useEffect, useState } from 'react';
import { api } from '@/api/client';
import type { HistoryDetail, HistoryItem, ModuleName, OutputFile } from '@/types';

const MODULES: { id: ModuleName | ''; label: string }[] = [
  { id: '', label: 'All' },
  { id: 'image', label: '🖼 Image' },
  { id: 'voice', label: '🔊 Voice' },
  { id: 'music', label: '🎵 Music' },
  { id: 'video', label: '🎬 Video' },
];

export default function History() {
  const [module, setModule] = useState<ModuleName | ''>('');
  const [items, setItems] = useState<HistoryItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [detail, setDetail] = useState<HistoryDetail | null>(null);

  const refresh = () => api.listHistory({ module: module || undefined, limit: 100 }).then(setItems).catch((e) => setError(String(e?.message ?? e)));
  useEffect(() => { refresh(); }, [module]);

  const onDelete = async (id: number) => {
    if (!confirm('Delete this history entry? (Files on disk are kept.)')) return;
    try { await api.deleteHistory(id); await refresh(); } catch (e: any) { setError(e?.message ?? String(e)); }
  };

  const onOpen = async (id: number) => {
    try { setDetail(await api.getHistory(id)); } catch (e: any) { setError(e?.message ?? String(e)); }
  };

  return (
    <>
      <div className="page-header">
        <div>
          <h2>History</h2>
          <div className="sub">All generation attempts, latest first. Click a row for full request / response payloads.</div>
        </div>
      </div>

      {error && <div className="toast error" style={{ position: 'static', marginBottom: 12 }}>{error}</div>}

      <div className="row" style={{ marginBottom: 12 }}>
        {MODULES.map((m) => (
          <button key={m.id || 'all'} className={m.id === module ? 'primary' : ''} onClick={() => setModule(m.id)}>{m.label}</button>
        ))}
        <div className="spacer" />
        <button onClick={refresh}>Refresh</button>
      </div>

      <div className="card">
        {items.length === 0 ? (
          <div className="empty">No history yet.</div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ textAlign: 'left', color: 'var(--text-dim)', fontSize: 12 }}>
                <th style={{ padding: '6px 8px' }}>#</th>
                <th style={{ padding: '6px 8px' }}>Module</th>
                <th style={{ padding: '6px 8px' }}>Prompt</th>
                <th style={{ padding: '6px 8px' }}>Status</th>
                <th style={{ padding: '6px 8px' }}>Files</th>
                <th style={{ padding: '6px 8px' }}>Time</th>
                <th style={{ padding: '6px 8px' }}></th>
              </tr>
            </thead>
            <tbody>
              {items.map((h) => (
                <tr key={h.id} style={{ borderTop: '1px solid var(--border)', cursor: 'pointer' }} onClick={() => onOpen(h.id)}>
                  <td style={{ padding: '8px' }}>{h.id}</td>
                  <td style={{ padding: '8px' }}><span className="tag">{h.module}</span></td>
                  <td style={{ padding: '8px', maxWidth: 480, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{h.prompt}</td>
                  <td style={{ padding: '8px' }}><span className={'tag ' + h.status}>{h.status}</span></td>
                  <td style={{ padding: '8px' }}>{h.output_files.length}</td>
                  <td style={{ padding: '8px' }} className="muted">{new Date(h.created_at).toLocaleString()}</td>
                  <td style={{ padding: '8px' }} onClick={(e) => e.stopPropagation()}>
                    <button className="danger" onClick={() => onDelete(h.id)}>Del</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {detail && <DetailModal detail={detail} onClose={() => setDetail(null)} />}
    </>
  );
}

function DetailModal({ detail, onClose }: { detail: HistoryDetail; onClose: () => void }) {
  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100 }} onClick={onClose}>
      <div className="card" style={{ width: 760, maxHeight: '90vh', overflow: 'auto' }} onClick={(e) => e.stopPropagation()}>
        <h3 style={{ marginTop: 0 }}>History #{detail.id} · <span className="tag">{detail.module}</span></h3>
        <div className="field"><label>Prompt</label><pre className="json" style={{ whiteSpace: 'pre-wrap' }}>{detail.prompt}</pre></div>
        <div className="field"><label>Status</label><span className={'tag ' + detail.status}>{detail.status}</span> · {detail.duration_ms}ms</div>

        {detail.error_message && <div className="field"><label>Error</label><pre className="json" style={{ color: 'var(--danger)' }}>{detail.error_message}</pre></div>}

        {detail.output_files.length > 0 && (
          <div className="field">
            <label>Output files</label>
            <div className="media-grid">
              {detail.output_files.map((f, i) => <DetailFile key={i} file={f} />)}
            </div>
          </div>
        )}

        <div className="grid-2">
          <div className="field">
            <label>Request payload</label>
            <pre className="json">{JSON.stringify(detail.request_payload, null, 2)}</pre>
          </div>
          <div className="field">
            <label>Response payload</label>
            <pre className="json">{JSON.stringify(detail.response_payload, null, 2)}</pre>
          </div>
        </div>

        <div className="row">
          <button className="ghost" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
}

function DetailFile({ file }: { file: OutputFile }) {
  const isImg = file.type === 'image' || (file.mime_type || '').startsWith('image/');
  const isVid = file.type === 'video' || (file.mime_type || '').startsWith('video/');
  const isAud = file.type === 'audio' || (file.mime_type || '').startsWith('audio/');
  const name = file.path ? file.path.split('/').pop() : file.url.split('?')[0].split('/').pop();
  return (
    <div className="media-card">
      {isImg && <img src={file.url} alt={name} />}
      {isVid && <video src={file.url} controls />}
      {isAud && <div style={{ padding: 16 }}><audio src={file.url} controls style={{ width: '100%' }} /></div>}
      <div className="meta">
        <span>{name}</span>
        <a href={file.url} download>download</a>
      </div>
    </div>
  );
}
