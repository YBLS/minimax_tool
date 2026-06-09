import { useEffect, useState } from 'react';
import { api } from '@/api/client';
import type { ApiConfig, ConfigTestResult, ConfigUpdate, ModuleName } from '@/types';
import { ConfigForm, FormSubmit } from './configForms/ConfigForm';

export default function ConfigCenter() {
  const [configs, setConfigs] = useState<ApiConfig[]>([]);
  const [editing, setEditing] = useState<ApiConfig | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<ConfigTestResult | null>(null);

  const refresh = () => api.listConfigs().then(setConfigs).catch((e) => setError(String(e?.message ?? e)));

  useEffect(() => { refresh(); }, []);

  const onSave = async (id: number, body: ConfigUpdate) => {
    try {
      await api.updateConfig(id, body);
      setEditing(null);
      await refresh();
    } catch (e: any) { setError(e?.message ?? String(e)); }
  };

  const onDelete = async (id: number) => {
    if (!confirm('Delete this config?')) return;
    try { await api.deleteConfig(id); await refresh(); } catch (e: any) { setError(e?.message ?? String(e)); }
  };

  const onTest = async (id: number) => {
    setTestResult(null);
    try {
      const r = await api.testConfig(id);
      setTestResult(r);
    } catch (e: any) { setTestResult({ ok: false, message: e?.message ?? String(e), latency_ms: 0 }); }
  };

  return (
    <>
      <div className="page-header">
        <div>
          <h2>Config Center</h2>
          <div className="sub">Each module has one config. API key is encrypted at rest; only <code>has_api_key</code> is exposed.</div>
        </div>
      </div>

      {error && <div className="toast error" style={{ position: 'static', marginBottom: 12 }}>{error}</div>}

      <div className="card">
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ textAlign: 'left', color: 'var(--text-dim)', fontSize: 12 }}>
              <th style={{ padding: '6px 8px' }}>Module</th>
              <th style={{ padding: '6px 8px' }}>Name</th>
              <th style={{ padding: '6px 8px' }}>Endpoint</th>
              <th style={{ padding: '6px 8px' }}>Model</th>
              <th style={{ padding: '6px 8px' }}>Key</th>
              <th style={{ padding: '6px 8px' }}>On</th>
              <th style={{ padding: '6px 8px' }}></th>
            </tr>
          </thead>
          <tbody>
            {configs.map((c) => (
              <tr key={c.id} style={{ borderTop: '1px solid var(--border)' }}>
                <td style={{ padding: '8px' }}><span className="tag">{c.module}</span></td>
                <td style={{ padding: '8px' }}>{c.display_name}</td>
                <td style={{ padding: '8px', fontFamily: 'ui-monospace, monospace', fontSize: 12 }}>
                  {c.base_url.replace(/^https?:\/\//, '')}{c.endpoint_path}
                </td>
                <td style={{ padding: '8px' }}>{c.model || '—'}</td>
                <td style={{ padding: '8px' }}>{c.has_api_key ? '🔑' : <span className="muted">empty</span>}</td>
                <td style={{ padding: '8px' }}>{c.enabled ? '✓' : '—'}</td>
                <td style={{ padding: '8px', textAlign: 'right' }}>
                  <button onClick={() => onTest(c.id)}>Test</button>{' '}
                  <button onClick={() => setEditing(c)}>Edit</button>{' '}
                  <button className="danger" onClick={() => onDelete(c.id)}>Del</button>
                </td>
              </tr>
            ))}
            {configs.length === 0 && <tr><td colSpan={7} className="empty">No configs yet.</td></tr>}
          </tbody>
        </table>

        {testResult && (
          <div className="toast" style={{ position: 'static', marginTop: 14, borderLeftColor: testResult.ok ? 'var(--success)' : 'var(--danger)' }}>
            <div><b>{testResult.ok ? 'OK' : 'Failed'}</b> · {testResult.latency_ms}ms</div>
            <div className="muted" style={{ marginTop: 4 }}>{testResult.message}</div>
            {testResult.sample_response && <pre className="json" style={{ marginTop: 8 }}>{JSON.stringify(testResult.sample_response, null, 2)}</pre>}
          </div>
        )}
      </div>

      {editing && (
        <EditModal
          config={editing}
          onClose={() => setEditing(null)}
          onSave={(body) => onSave(editing.id, body)}
        />
      )}
    </>
  );
}

function EditModal({ config, onClose, onSave }: { config: ApiConfig; onClose: () => void; onSave: (b: ConfigUpdate) => void }) {
  const [pending, setPending] = useState<FormSubmit | null>(null);
  const [error, setError] = useState<string | null>(null);

  const save = () => {
    if (!pending) return;
    // Sanity-check the JSON pieces if user touched them
    try {
      // Re-parse to ensure valid JSON
      JSON.stringify(pending.request_template);
      JSON.stringify(pending.response_parser);
      JSON.stringify(pending.default_params);
    } catch (e: any) {
      setError(`Invalid form state: ${e.message}`);
      return;
    }
    onSave(pending);
  };

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100,
    }} onClick={onClose}>
      <div className="card" style={{ width: 720, maxHeight: '90vh', overflow: 'auto' }} onClick={(e) => e.stopPropagation()}>
        <h3 style={{ marginTop: 0 }}>Edit · {config.module} · {config.display_name}</h3>
        {error && <div className="toast error" style={{ position: 'static', marginBottom: 10 }}>{error}</div>}

        <ConfigForm
          config={config}
          onChange={setPending}
        />

        <div className="row" style={{ marginTop: 16 }}>
          <button className="primary" onClick={save} disabled={!pending}>Save</button>
          <button className="ghost" onClick={onClose}>Cancel</button>
        </div>
      </div>
    </div>
  );
}
