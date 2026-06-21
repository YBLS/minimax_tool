import { useEffect, useState } from 'react';
import {
  Alert,
  Button,
  Card,
  Empty,
  Popconfirm,
  Segmented,
  Space,
  Table,
  Tag,
  Typography,
  App as AntdApp,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { ReloadOutlined, DeleteOutlined } from '@ant-design/icons';
import { api } from '@/api/client';
import type { HistoryDetail, HistoryItem, ModuleName, OutputFile } from '@/types';

const MODULE_FILTERS: { id: ModuleName | ''; label: string }[] = [
  { id: '',         label: 'All' },
  { id: 'translate', label: '🌐 Translate' },
  { id: 'image',     label: '🖼 Image' },
  { id: 'voice',     label: '🔊 Voice' },
  { id: 'music',     label: '🎵 Music' },
  { id: 'video',     label: '🎬 Video' },
];

const STATUS_COLOR: Record<string, string> = {
  success: 'success',
  failed: 'error',
  running: 'processing',
  pending: 'default',
};

export default function History() {
  const { message } = AntdApp.useApp();
  // Free-form string — the History page offers "Translate" alongside the
  // well-known modules (image/voice/music/video) and ModuleName would force
  // a type-cast for that one filter chip. The backend matches: listHistory
  // accepts any string, since generation_history.module is VARCHAR(50).
  const [module, setModule] = useState<ModuleName | 'translate' | ''>('');
  const [items, setItems] = useState<HistoryItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [detail, setDetail] = useState<HistoryDetail | null>(null);
  const [loading, setLoading] = useState(false);

  const refresh = () => {
    setLoading(true);
    api.listHistory({ module: module || undefined, limit: 100 })
      .then(setItems)
      .catch((e) => setError(String(e?.message ?? e)))
      .finally(() => setLoading(false));
  };

  useEffect(() => { refresh(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [module]);

  const onDelete = async (id: number) => {
    try {
      await api.deleteHistory(id);
      message.success(`Deleted #${id}`);
      await refresh();
    } catch (e: any) {
      setError(e?.message ?? String(e));
    }
  };

  const onOpen = async (id: number) => {
    try {
      setDetail(await api.getHistory(id));
    } catch (e: any) {
      setError(e?.message ?? String(e));
    }
  };

  const columns: ColumnsType<HistoryItem> = [
    { title: '#', dataIndex: 'id', width: 60 },
    {
      title: 'Module',
      dataIndex: 'module',
      width: 110,
      render: (v: string) => <Tag>{v}</Tag>,
    },
    {
      title: 'Prompt',
      dataIndex: 'prompt',
      ellipsis: true,
      render: (v: string) => <span>{v || <Typography.Text type="secondary">—</Typography.Text>}</span>,
    },
    {
      title: 'Status',
      dataIndex: 'status',
      width: 110,
      render: (v: string) => <Tag color={STATUS_COLOR[v] ?? 'default'}>{v}</Tag>,
    },
    {
      title: 'Files',
      dataIndex: 'output_files',
      width: 80,
      render: (files: OutputFile[]) => files.length,
    },
    {
      title: 'Time',
      dataIndex: 'created_at',
      width: 180,
      render: (v: string) => (
        <Typography.Text type="secondary">{new Date(v).toLocaleString()}</Typography.Text>
      ),
    },
    {
      title: '',
      key: 'actions',
      width: 110,
      align: 'right',
      render: (_: any, h: HistoryItem) => (
        <Popconfirm
          title="Delete this history entry?"
          description="Files on disk are kept."
          onConfirm={() => onDelete(h.id)}
          okText="Delete"
          okButtonProps={{ danger: true }}
          onCancel={(e) => e?.stopPropagation()}
        >
          <Button
            size="small"
            danger
            icon={<DeleteOutlined />}
            onClick={(e) => e.stopPropagation()}
          />
        </Popconfirm>
      ),
    },
  ];

  return (
    <>
      <div className="page-title">
        <div>
          <h2>⌛ History</h2>
          <div className="page-sub">
            All generation attempts, latest first. Click a row for full request / response payloads.
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

      <Space style={{ marginBottom: 12 }} wrap>
        <Segmented
          value={module}
          onChange={(v) => setModule(v as ModuleName | '')}
          options={MODULE_FILTERS.map((m) => ({ value: m.id, label: m.label }))}
        />
        <Button icon={<ReloadOutlined />} onClick={refresh}>Refresh</Button>
      </Space>

      <Card bodyStyle={{ padding: 0 }}>
        <Table<HistoryItem>
          rowKey="id"
          columns={columns}
          dataSource={items}
          loading={loading}
          pagination={false}
          onRow={(h) => ({ onClick: () => onOpen(h.id), style: { cursor: 'pointer' } })}
          locale={{
            emptyText: <Empty description="No history yet." style={{ padding: 32 }} />,
          }}
        />
      </Card>

      {detail && <DetailDrawer detail={detail} onClose={() => setDetail(null)} />}
    </>
  );
}

function DetailDrawer({
  detail,
  onClose,
}: {
  detail: HistoryDetail;
  onClose: () => void;
}) {
  return (
    <div
      style={{
        position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)',
        zIndex: 1000, display: 'flex', justifyContent: 'flex-end',
      }}
      onClick={onClose}
    >
      <div
        style={{
          width: 720, maxWidth: '100%', height: '100%',
          background: 'var(--ant-color-bg-container, #fff)',
          boxShadow: '-8px 0 24px rgba(0,0,0,0.15)',
          overflowY: 'auto', padding: 24,
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <Space style={{ marginBottom: 12 }}>
          <Typography.Title level={4} style={{ margin: 0 }}>
            History #{detail.id}
          </Typography.Title>
          <Tag>{detail.module}</Tag>
          <Tag color={STATUS_COLOR[detail.status] ?? 'default'}>{detail.status}</Tag>
          <Typography.Text type="secondary">{detail.duration_ms}ms</Typography.Text>
        </Space>

        <section style={{ marginBottom: 16 }}>
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>PROMPT</Typography.Text>
          <pre className="json-block" style={{ marginTop: 4 }}>{detail.prompt || '—'}</pre>
        </section>

        {detail.error_message && (
          <section style={{ marginBottom: 16 }}>
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>ERROR</Typography.Text>
            <pre className="json-block" style={{ marginTop: 4, color: '#f87171' }}>{detail.error_message}</pre>
          </section>
        )}

        {detail.output_files.length > 0 && (
          <section style={{ marginBottom: 16 }}>
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>OUTPUT FILES</Typography.Text>
            <div className="media-grid" style={{ marginTop: 4 }}>
              {detail.output_files.map((f, i) => <DetailFile key={i} file={f} />)}
            </div>
          </section>
        )}

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 16 }}>
          <section>
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>REQUEST</Typography.Text>
            <pre className="json-block" style={{ marginTop: 4 }}>
              {JSON.stringify(detail.request_payload, null, 2)}
            </pre>
          </section>
          <section>
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>RESPONSE</Typography.Text>
            <pre className="json-block" style={{ marginTop: 4 }}>
              {JSON.stringify(detail.response_payload, null, 2)}
            </pre>
          </section>
        </div>

        <Button onClick={onClose}>Close</Button>
      </div>
    </div>
  );
}

function DetailFile({ file }: { file: OutputFile }) {
  const isImg = file.type === 'image' || (file.mime_type || '').startsWith('image/');
  const isVid = file.type === 'video' || (file.mime_type || '').startsWith('video/');
  const isAud = file.type === 'audio' || (file.mime_type || '').startsWith('audio/');
  const name = file.path
    ? file.path.split('/').pop()
    : file.url.split('?')[0].split('/').pop();
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
