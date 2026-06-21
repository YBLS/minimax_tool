import { useEffect, useState } from 'react';
import {
  Alert,
  Button,
  Card,
  Empty,
  Input,
  Popconfirm,
  Space,
  Switch,
  Table,
  Tabs,
  Tag,
  Tooltip,
  Typography,
  App as AntdApp,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import {
  ApiOutlined,
  DeleteOutlined,
  EditOutlined,
  KeyOutlined,
  PlusOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import { api } from '@/api/client';
import type {
  ApiConfig,
  ConfigTestResult,
  ConfigUpdate,
  KeyProvider,
  KeyProviderTestResult,
  KeyProviderUpdate,
  ModuleName,
} from '@/types';
import { ConfigForm, FormSubmit } from './configForms/ConfigForm';

const MODULE_TAG_COLOR: Record<string, string> = {
  image: 'magenta',
  voice: 'orange',
  music: 'cyan',
  video: 'geekblue',
  translate: 'purple',
};

export default function ConfigCenter() {
  const { message } = AntdApp.useApp();
  const [configs, setConfigs] = useState<ApiConfig[]>([]);
  // The Key column needs to distinguish "no provider at all" from
  // "ambiguous (2+ enabled providers)" — both have has_api_key=false on
  // the config row, so we look at the provider list ourselves.
  const [providers, setProviders] = useState<KeyProvider[]>([]);
  const [editing, setEditing] = useState<ApiConfig | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<ConfigTestResult | null>(null);

  const refresh = () =>
    Promise.all([api.listConfigs(), api.listKeyProviders()])
      .then(([cfgs, provs]) => {
        setConfigs(cfgs);
        setProviders(provs);
      })
      .catch((e) => setError(String(e?.message ?? e)));

  useEffect(() => { refresh(); }, []);

  const onSave = async (id: number, body: ConfigUpdate) => {
    try {
      await api.updateConfig(id, body);
      setEditing(null);
      await refresh();
      message.success('Config saved');
    } catch (e: any) { setError(e?.message ?? String(e)); }
  };

  const onDelete = async (id: number) => {
    try {
      await api.deleteConfig(id);
      await refresh();
      message.success('Config deleted');
    } catch (e: any) { setError(e?.message ?? String(e)); }
  };

  const onTest = async (id: number) => {
    setTestResult(null);
    try {
      const r = await api.testConfig(id);
      setTestResult(r);
      if (r.ok) message.success(`OK · ${r.latency_ms}ms`);
    } catch (e: any) {
      const r: ConfigTestResult = { ok: false, message: e?.message ?? String(e), latency_ms: 0 };
      setTestResult(r);
    }
  };

  const columns: ColumnsType<ApiConfig> = [
    {
      title: 'Module',
      dataIndex: 'module',
      width: 110,
      render: (v: string) => <Tag color={MODULE_TAG_COLOR[v] ?? 'default'}>{v}</Tag>,
    },
    { title: 'Name', dataIndex: 'display_name' },
    {
      title: 'Endpoint',
      dataIndex: 'base_url',
      render: (_: any, c: ApiConfig) => (
        <Typography.Text style={{ fontFamily: 'ui-monospace, monospace', fontSize: 12 }}>
          {c.base_url.replace(/^https?:\/\//, '')}{c.endpoint_path}
        </Typography.Text>
      ),
    },
    { title: 'Model', dataIndex: 'model', width: 200, render: (v: string) => v || '—' },
    {
      title: 'API Key',
      dataIndex: 'key_provider_name',
      width: 220,
      render: (_: any, c: ApiConfig) => {
        // The column has 4 visible states. `has_api_key` is the runtime
        // verdict (covers both explicit binding and the auto-bind path),
        // but we still need the provider count to disambiguate the two
        // "has_api_key=false" cases below.
        const enabledWithKey = providers.filter((p) => p.enabled && p.has_api_key);
        if (c.has_api_key) {
          // Resolves to a real key either via explicit binding or auto-bind.
          if (c.key_provider_id) {
            return <Tag color="success" icon={<KeyOutlined />}>
              {c.key_provider_name ?? '(unnamed provider)'}
            </Tag>;
          }
          // Auto-bind path. Show the *only* enabled provider name as a hint
          // for what'll actually be used.
          return <Tooltip
            title={enabledWithKey.length === 1
              ? `Will use the only enabled provider: ${enabledWithKey[0].name}`
              : 'Auto-binds to the single enabled provider at request time.'}
          >
            <Tag color="success" icon={<KeyOutlined />}>auto-bind</Tag>
          </Tooltip>;
        }
        if (c.key_provider_id) {
          // Bound, but the bound provider has no key saved. If other
          // providers exist, the user can switch the binding in Edit.
          return <Tooltip title={`Provider #${c.key_provider_id} has no key saved. Edit this config to switch bindings or add a key on the API Keys tab.`}>
            <Tag color="warning" icon={<KeyOutlined />}>provider empty</Tag>
          </Tooltip>;
        }
        if (enabledWithKey.length === 0) {
          // Nothing usable anywhere — guide the user to the API Keys tab.
          return <Tooltip title="No key provider is configured. Create one in the API Keys tab.">
            <Tag>no key</Tag>
          </Tooltip>;
        }
        // 2+ enabled providers with keys — auto-bind would error out as
        // ambiguous. The user must bind explicitly via Edit.
        return <Tooltip title={`${enabledWithKey.length} enabled providers exist. Auto-bind is ambiguous; edit this config to pick one.`}>
          <Tag color="warning">ambiguous — pick one</Tag>
        </Tooltip>;
      },
    },
    {
      title: 'On',
      dataIndex: 'enabled',
      width: 70,
      render: (v: boolean) => (v ? '✓' : '—'),
    },
    {
      title: '',
      key: 'actions',
      width: 220,
      align: 'right',
      render: (_: any, c: ApiConfig) => (
        <Space>
          <Button size="small" icon={<ThunderboltOutlined />} onClick={() => onTest(c.id)}>
            Test
          </Button>
          <Button size="small" icon={<EditOutlined />} onClick={() => setEditing(c)}>
            Edit
          </Button>
          <Popconfirm
            title="Delete this config?"
            onConfirm={() => onDelete(c.id)}
            okText="Delete"
            okButtonProps={{ danger: true }}
          >
            <Button size="small" danger icon={<DeleteOutlined />}>
              Del
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <>
      <div className="page-title">
        <div>
          <h2>
            <ApiOutlined /> Config Center
          </h2>
          <div className="page-sub">
            API keys live in the <code>key_providers</code> table (decoupled from module configs).
            A config with no <code>key_provider_id</code> auto-binds to the only enabled provider.
          </div>
        </div>
      </div>

      {error && (
        <Alert
          type="error"
          showIcon
          closable
          message={error}
          onClose={() => setError(null)}
          style={{ marginBottom: 16 }}
        />
      )}

      <Tabs
        defaultActiveKey="configs"
        items={[
          {
            key: 'configs',
            label: 'Module Configs',
            children: (
              <Card bodyStyle={{ padding: 0 }}>
                <Table<ApiConfig>
                  rowKey="id"
                  columns={columns}
                  dataSource={configs}
                  pagination={false}
                  locale={{
                    emptyText: <Empty description="No configs yet." style={{ padding: 32 }} />,
                  }}
                />
              </Card>
            ),
          },
          {
            key: 'keys',
            label: <span><KeyOutlined /> API Keys</span>,
            children: <KeyProvidersTab onError={setError} />,
          },
        ]}
      />

      {testResult && (
        <Card style={{ marginTop: 16 }}>
          <Space style={{ marginBottom: 4 }}>
            <Tag color={testResult.ok ? 'success' : 'error'}>
              {testResult.ok ? 'OK' : 'Failed'}
            </Tag>
            <Typography.Text type="secondary">{testResult.latency_ms}ms</Typography.Text>
          </Space>
          <div className="field-hint" style={{ marginBottom: testResult.sample_response ? 8 : 0 }}>
            {testResult.message}
          </div>
          {testResult.sample_response && (
            <pre className="json-block">
              {JSON.stringify(testResult.sample_response, null, 2)}
            </pre>
          )}
        </Card>
      )}

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

// -------------------- API Keys tab --------------------

function KeyProvidersTab({ onError }: { onError: (s: string) => void }) {
  const { message } = AntdApp.useApp();
  const [providers, setProviders] = useState<KeyProvider[]>([]);
  const [editing, setEditing] = useState<KeyProvider | null>(null);
  const [creating, setCreating] = useState(false);
  const [testResult, setTestResult] = useState<KeyProviderTestResult | null>(null);

  const refresh = () =>
    api.listKeyProviders()
      .then(setProviders)
      .catch((e) => onError(String(e?.message ?? e)));

  useEffect(() => { refresh(); }, []);

  const onDelete = async (id: number) => {
    try {
      await api.deleteKeyProvider(id);
      await refresh();
      message.success('Provider deleted');
    } catch (e: any) { onError(e?.message ?? String(e)); }
  };

  const onTest = async (id: number) => {
    setTestResult(null);
    try {
      const r = await api.testKeyProvider(id);
      setTestResult(r);
      if (r.ok) message.success(`OK · ${r.latency_ms}ms`);
    } catch (e: any) {
      setTestResult({ ok: false, message: e?.message ?? String(e), latency_ms: 0 });
    }
  };

  const onToggleEnabled = async (p: KeyProvider, enabled: boolean) => {
    try {
      await api.updateKeyProvider(p.id, { enabled });
      await refresh();
    } catch (e: any) { onError(e?.message ?? String(e)); }
  };

  const columns: ColumnsType<KeyProvider> = [
    { title: 'Name', dataIndex: 'name', width: 200 },
    {
      title: 'Description',
      dataIndex: 'description',
      render: (v: string) => {
        if (!v) return <Typography.Text type="secondary">—</Typography.Text>;
        const migrated = v.startsWith("Migrated from app_secrets");
        if (migrated) {
          // The first line of the auto-generated description is the most
          // user-facing detail; show it on hover.
          return (
            <Tooltip title={v}>
              <span>
                <Tag color="default" style={{ marginRight: 6 }}>Migrated from app_secrets</Tag>
                <Typography.Text type="secondary">
                  from Secrets page
                </Typography.Text>
              </span>
            </Tooltip>
          );
        }
        return v;
      },
    },
    {
      title: 'Key',
      dataIndex: 'has_api_key',
      width: 90,
      render: (v: boolean) =>
        v ? <Tag color="success" icon={<KeyOutlined />}>set</Tag>
           : <Typography.Text type="secondary">empty</Typography.Text>,
    },
    {
      title: 'Enabled',
      dataIndex: 'enabled',
      width: 90,
      render: (v: boolean, p: KeyProvider) => (
        <Switch size="small" checked={v} onChange={(c) => onToggleEnabled(p, c)} />
      ),
    },
    {
      title: '',
      key: 'actions',
      width: 220,
      align: 'right',
      render: (_: any, p: KeyProvider) => (
        <Space>
          <Button size="small" icon={<ThunderboltOutlined />} onClick={() => onTest(p.id)}>
            Test
          </Button>
          <Button size="small" icon={<EditOutlined />} onClick={() => setEditing(p)}>
            Edit
          </Button>
          <Popconfirm
            title="Delete this provider?"
            description="Configs linked to it will lose their key binding. Auto-bind will pick up if exactly one other enabled provider exists."
            onConfirm={() => onDelete(p.id)}
            okText="Delete"
            okButtonProps={{ danger: true }}
          >
            <Button size="small" danger icon={<DeleteOutlined />}>
              Del
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <>
      {providers.some((p) => p.description?.startsWith("Migrated from app_secrets")) && (
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
          message="Some providers here were migrated from the old Secrets page"
          description={
            <>
              Rows tagged <Tag color="default">Migrated from app_secrets</Tag> were
              auto-promoted on app start. You can rename, delete, or add more providers
              freely — the original Secrets rows still exist but are no longer read by
              the modules.
            </>
          }
        />
      )}
      <Card
        bodyStyle={{ padding: 0 }}
        title={
          <Space>
            <span>API Key Providers</span>
            <Typography.Text type="secondary" style={{ fontWeight: 'normal', fontSize: 12 }}>
              Each module config references one of these via <code>key_provider_id</code>.
              Leave the binding empty to auto-bind to the only enabled provider.
            </Typography.Text>
          </Space>
        }
        extra={
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => setCreating(true)}
          >
            New provider
          </Button>
        }
      >
        <Table<KeyProvider>
          rowKey="id"
          columns={columns}
          dataSource={providers}
          pagination={false}
          locale={{
            emptyText: (
              <Empty
                description="No providers yet. Create one to start using the API."
                style={{ padding: 32 }}
              />
            ),
          }}
        />
      </Card>

      {testResult && (
        <Card style={{ marginTop: 16 }}>
          <Space style={{ marginBottom: 4 }}>
            <Tag color={testResult.ok ? 'success' : 'error'}>
              {testResult.ok ? 'OK' : 'Failed'}
            </Tag>
            <Typography.Text type="secondary">{testResult.latency_ms}ms</Typography.Text>
          </Space>
          <div className="field-hint" style={{ marginBottom: testResult.sample_response ? 8 : 0 }}>
            {testResult.message}
          </div>
          {testResult.sample_response && (
            <pre className="json-block">
              {JSON.stringify(testResult.sample_response, null, 2)}
            </pre>
          )}
        </Card>
      )}

      {creating && (
        <ProviderModal
          onClose={() => setCreating(false)}
          onSave={async (body) => {
            try {
              await api.createKeyProvider(body);
              setCreating(false);
              await refresh();
              message.success('Provider created');
            } catch (e: any) { onError(e?.message ?? String(e)); }
          }}
        />
      )}

      {editing && (
        <ProviderModal
          provider={editing}
          onClose={() => setEditing(null)}
          onSave={async (body) => {
            try {
              await api.updateKeyProvider(editing.id, body as KeyProviderUpdate);
              setEditing(null);
              await refresh();
              message.success('Provider saved');
            } catch (e: any) { onError(e?.message ?? String(e)); }
          }}
        />
      )}
    </>
  );
}

function ProviderModal({
  provider,
  onClose,
  onSave,
}: {
  provider?: KeyProvider;
  onClose: () => void;
  onSave: (b: { name: string; description: string; api_key: string; enabled: boolean }) => void;
}) {
  const [name, setName] = useState(provider?.name ?? '');
  const [description, setDescription] = useState(provider?.description ?? '');
  const [apiKey, setApiKey] = useState('');
  const [enabled, setEnabled] = useState(provider?.enabled ?? true);
  const [error, setError] = useState<string | null>(null);

  const save = () => {
    if (!name.trim()) { setError('Name is required'); return; }
    if (!provider && !apiKey.trim()) {
      setError('API key is required for a new provider (use Edit later to clear it)');
      return;
    }
    setError(null);
    onSave({
      name: name.trim(),
      description: description.trim(),
      api_key: apiKey,  // empty string is fine for edit (= clear)
      enabled,
    });
  };

  return (
    <div
      style={{
        position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)',
        zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}
      onClick={onClose}
    >
      <div
        style={{
          width: 560, maxWidth: '100%', maxHeight: '90vh', overflow: 'auto',
          background: 'var(--ant-color-bg-container, #fff)',
          borderRadius: 8, boxShadow: '0 12px 32px rgba(0,0,0,0.2)', padding: 24,
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <Typography.Title level={4} style={{ marginTop: 0 }}>
          {provider ? `Edit provider · ${provider.name}` : 'New key provider'}
        </Typography.Title>
        {error && (
          <Alert
            type="error"
            showIcon
            closable
            message={error}
            onClose={() => setError(null)}
            style={{ marginBottom: 12 }}
          />
        )}
        <Space direction="vertical" style={{ width: '100%' }}>
          <div>
            <label className="field-label">Name</label>
            <Input
              placeholder="e.g. prod-minimax"
              value={name}
              onChange={(e) => setName(e.target.value)}
              maxLength={100}
            />
          </div>
          <div>
            <label className="field-label">Description (optional)</label>
            <Input
              placeholder="What is this key for?"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>
          <div>
            <label className="field-label">API Key</label>
            <Input.Password
              placeholder={
                provider
                  ? (provider.has_api_key ? 'leave blank to keep current' : 'paste key here')
                  : 'paste key here'
              }
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
            />
            {provider?.has_api_key && (
              <div className="field-hint" style={{ marginTop: 4 }}>
                A key is already set. Leave blank to keep it; clear the field to remove it.
              </div>
            )}
          </div>
          <div>
            <Space>
              <Switch checked={enabled} onChange={setEnabled} />
              <Typography.Text>Enabled</Typography.Text>
            </Space>
          </div>
        </Space>
        <Space style={{ marginTop: 16 }}>
          <Button type="primary" onClick={save}>Save</Button>
          <Button onClick={onClose}>Cancel</Button>
        </Space>
      </div>
    </div>
  );
}

// -------------------- Edit config modal (unchanged shape) --------------------

function EditModal({
  config,
  onClose,
  onSave,
}: {
  config: ApiConfig;
  onClose: () => void;
  onSave: (b: ConfigUpdate) => void;
}) {
  const [pending, setPending] = useState<FormSubmit | null>(null);
  const [error, setError] = useState<string | null>(null);

  const save = () => {
    if (!pending) return;
    try {
      JSON.stringify(pending.request_template);
      JSON.stringify(pending.response_parser);
      JSON.stringify(pending.default_params);
    } catch (e: any) {
      setError(`Invalid form state: ${e.message}`);
      return;
    }
    onSave(pending as unknown as ConfigUpdate);
  };

  return (
    <div
      style={{
        position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)',
        zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}
      onClick={onClose}
    >
      <div
        style={{
          width: 760, maxWidth: '100%', maxHeight: '90vh', overflow: 'auto',
          background: 'var(--ant-color-bg-container, #fff)',
          borderRadius: 8, boxShadow: '0 12px 32px rgba(0,0,0,0.2)', padding: 24,
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <Typography.Title level={4} style={{ marginTop: 0 }}>
          Edit · {config.module} · {config.display_name}
        </Typography.Title>
        {error && (
          <Alert
            type="error"
            showIcon
            closable
            message={error}
            onClose={() => setError(null)}
            style={{ marginBottom: 12 }}
          />
        )}
        <ConfigForm config={config} onChange={setPending} />
        <Space style={{ marginTop: 16 }}>
          <Button type="primary" onClick={save} disabled={!pending}>
            Save
          </Button>
          <Button onClick={onClose}>Cancel</Button>
        </Space>
      </div>
    </div>
  );
}
