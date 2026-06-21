import { useEffect, useState } from 'react';
import {
  Alert,
  Button,
  Card,
  Empty,
  Form,
  Input,
  Modal,
  Space,
  Table,
  Tag,
  Typography,
  Popconfirm,
  App as AntdApp,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { PlusOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons';
import { api } from '@/api/client';
import type { SecretMeta } from '@/types';

interface FormValues {
  name: string;
  value?: string;
  description?: string;
}

export default function Secrets() {
  const { message } = AntdApp.useApp();
  const [secrets, setSecrets] = useState<SecretMeta[]>([]);
  const [editing, setEditing] = useState<SecretMeta | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = () =>
    api.listSecrets()
      .then(setSecrets)
      .catch((e) => setError(String(e?.message ?? e)));

  useEffect(() => { refresh(); }, []);

  const onSave = async (name: string, value: string | undefined, description: string) => {
    try {
      await api.upsertSecret(name, value ?? '', description);
      setEditing(null);
      await refresh();
      message.success('Secret saved');
    } catch (e: any) {
      setError(e?.message ?? String(e));
    }
  };

  const onDelete = async (name: string) => {
    try {
      await api.deleteSecret(name);
      await refresh();
      message.success(`Deleted ${name}`);
    } catch (e: any) {
      setError(e?.message ?? String(e));
    }
  };

  const columns: ColumnsType<SecretMeta> = [
    {
      title: 'Name',
      dataIndex: 'name',
      render: (v: string) => <code>{v}</code>,
      width: 220,
    },
    {
      title: 'Description',
      dataIndex: 'description',
      render: (v: string) => v || <Typography.Text type="secondary">—</Typography.Text>,
    },
    {
      title: 'Has value',
      dataIndex: 'has_value',
      width: 110,
      render: (v: boolean) =>
        v ? <Tag color="success">✓ set</Tag> : <Tag>empty</Tag>,
    },
    {
      title: 'Updated',
      dataIndex: 'updated_at',
      width: 180,
      render: (v: string) => <Typography.Text type="secondary">{new Date(v).toLocaleString()}</Typography.Text>,
    },
    {
      title: '',
      key: 'actions',
      width: 160,
      align: 'right',
      render: (_: any, s: SecretMeta) => (
        <Space>
          <Button size="small" icon={<EditOutlined />} onClick={() => setEditing(s)}>
            Edit
          </Button>
          <Popconfirm
            title={`Delete secret "${s.name}"?`}
            onConfirm={() => onDelete(s.name)}
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
          <h2>🔑 Secrets</h2>
          <div className="page-sub">
            A small encrypted key/value store for any extra credentials
            you want to manage (e.g. an upstream proxy key, a webhook
            secret, etc.).
          </div>
        </div>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() =>
            setEditing({
              name: '',
              description: '',
              has_value: false,
              created_at: '',
              updated_at: '',
            })
          }
        >
          New secret
        </Button>
      </div>

      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message="Module API keys (image / voice / music / video / translate) live in Config Center → API Keys, not here."
        description={
          <>
            If you previously saved your MiniMax API key on this page,
            it was automatically promoted into a <b>key provider</b> on
            the next app start. Look for an entry named after your old
            secret under <b>Config Center → API Keys</b> — you can rename
            it, delete it, or add more from there.
          </>
        }
      />

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

      <Card bodyStyle={{ padding: 0 }}>
        <Table<SecretMeta>
          rowKey="name"
          columns={columns}
          dataSource={secrets}
          pagination={false}
          locale={{
            emptyText: (
              <Empty
                description="No secrets yet. The 4 module API keys live in the Config Center, not here."
                style={{ padding: 32 }}
              />
            ),
          }}
        />
      </Card>

      {editing && (
        <SecretModal
          secret={editing}
          onClose={() => setEditing(null)}
          onSave={onSave}
        />
      )}
    </>
  );
}

function SecretModal({
  secret,
  onClose,
  onSave,
}: {
  secret: SecretMeta;
  onClose: () => void;
  onSave: (name: string, value: string | undefined, description: string) => void;
}) {
  const isNew = !secret.created_at;
  const [form] = Form.useForm<FormValues>();

  return (
    <Modal
      open
      title={isNew ? 'New secret' : `Edit secret · ${secret.name}`}
      onCancel={onClose}
      okText="Save"
      onOk={async () => {
        const v = await form.validateFields();
        onSave(v.name.trim(), v.value, v.description ?? '');
      }}
      width={480}
      destroyOnClose
    >
      <Form<FormValues>
        form={form}
        layout="vertical"
        initialValues={{
          name: secret.name,
          value: '',
          description: secret.description,
        }}
      >
        <Form.Item
          name="name"
          label="Name"
          rules={[{ required: true, message: 'Name is required' }]}
        >
          <Input disabled={!isNew} placeholder="e.g. proxy_api_key" />
        </Form.Item>
        <Form.Item
          name="value"
          label={
            <Space>
              Value
              {secret.has_value && (
                <Typography.Text type="secondary" style={{ fontWeight: 'normal' }}>
                  · blank to keep
                </Typography.Text>
              )}
            </Space>
          }
          rules={isNew ? [{ required: true, message: 'Value is required' }] : []}
        >
          <Input.Password
            placeholder={secret.has_value ? '••••••••' : 'paste value'}
            autoComplete="off"
            spellCheck={false}
          />
        </Form.Item>
        <Form.Item name="description" label="Description">
          <Input />
        </Form.Item>
      </Form>
    </Modal>
  );
}
