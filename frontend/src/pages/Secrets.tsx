import { useEffect, useState } from 'react';
import { api } from '@/api/client';
import type { SecretMeta } from '@/types';

export default function Secrets() {
  const [secrets, setSecrets] = useState<SecretMeta[]>([]);
  const [editing, setEditing] = useState<SecretMeta | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = () => api.listSecrets().then(setSecrets).catch((e) => setError(String(e?.message ?? e)));
  useEffect(() => { refresh(); }, []);

  const onSave = async (name: string, value: string, description: string) => {
    try { await api.upsertSecret(name, value, description); setEditing(null); await refresh(); }
    catch (e: any) { setError(e?.message ?? String(e)); }
  };

  const onDelete = async (name: string) => {
    if (!confirm(`Delete secret "${name}"?`)) return;
    try { await api.deleteSecret(name); await refresh(); } catch (e: any) { setError(e?.message ?? String(e)); }
  };

  return (
    <>
      <div className="page-header">
        <div>
          <h2>Secrets</h2>
          <div className="sub">A small encrypted key/value store for any extra credentials you want to manage (e.g. an upstream proxy key).</div>
        </div>
        <button className="primary" onClick={() => setEditing({ name: '', description: '', has_value: false, created_at: '', updated_at: '' })}>+ New secret</button>
      </div>

      {error && <div className="toast error" style={{ position: 'static', marginBottom: 12 }}>{error}</div>}

      <div className="card">
        {secrets.length === 0 ? (
          <div className="empty">No secrets yet. The 4 module API keys live in the Config Center, not here.</div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ textAlign: 'left', color: 'var(--text-dim)', fontSize: 12 }}>
                <th style={{ padding: '6px 8px' }}>Name</th>
                <th style={{ padding: '6px 8px' }}>Description</th>
                <th style={{ padding: '6px 8px' }}>Has value</th>
                <th style={{ padding: '6px 8px' }}>Updated</th>
                <th style={{ padding: '6px 8px' }}></th>
              </tr>
            </thead>
            <tbody>
              {secrets.map((s) => (
                <tr key={s.name} style={{ borderTop: '1px solid var(--border)' }}>
                  <td style={{ padding: '8px', fontFamily: 'ui-monospace, monospace' }}>{s.name}</td>
                  <td style={{ padding: '8px' }}>{s.description || <span className="muted">—</span>}</td>
                  <td style={{ padding: '8px' }}>{s.has_value ? '✓' : '—'}</td>
                  <td style={{ padding: '8px' }} className="muted">{new Date(s.updated_at).toLocaleString()}</td>
                  <td style={{ padding: '8px', textAlign: 'right' }}>
                    <button onClick={() => setEditing(s)}>Edit</button>{' '}
                    <button className="danger" onClick={() => onDelete(s.name)}>Del</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {editing && <SecretModal secret={editing} onClose={() => setEditing(null)} onSave={onSave} />}
    </>
  );
}

function SecretModal({ secret, onClose, onSave }: { secret: SecretMeta; onClose: () => void; onSave: (name: string, value: string, desc: string) => void }) {
  const isNew = !secret.created_at;
  const [name, setName] = useState(secret.name);
  const [value, setValue] = useState('');
  const [description, setDescription] = useState(secret.description);
  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100 }} onClick={onClose}>
      <div className="card" style={{ width: 480 }} onClick={(e) => e.stopPropagation()}>
        <h3 style={{ marginTop: 0 }}>{isNew ? 'New' : 'Edit'} secret</h3>
        <div className="field">
          <label>Name</label>
          <input value={name} disabled={!isNew} onChange={(e) => setName(e.target.value)} placeholder="e.g. proxy_api_key" />
        </div>
        <div className="field">
          <label>Value {secret.has_value && <span className="muted" style={{ textTransform: 'none' }}>· blank to keep</span>}</label>
          <input type="password" value={value} onChange={(e) => setValue(e.target.value)} placeholder={secret.has_value ? '••••••••' : 'paste value'} />
        </div>
        <div className="field">
          <label>Description</label>
          <input value={description} onChange={(e) => setDescription(e.target.value)} />
        </div>
        <div className="row">
          <button className="primary" disabled={!name || (!isNew && !value)} onClick={() => onSave(name, value, description)}>Save</button>
          <button className="ghost" onClick={onClose}>Cancel</button>
        </div>
      </div>
    </div>
  );
}
