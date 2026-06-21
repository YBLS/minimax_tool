import { useEffect, useMemo, useState } from 'react';
import {
  AutoComplete,
  Button,
  Card,
  Input,
  Select,
  Space,
  Tooltip,
  Typography,
  message,
  Alert,
  Tag,
} from 'antd';
import {
  SwapOutlined,
  ThunderboltOutlined,
  ClearOutlined,
  CopyOutlined,
} from '@ant-design/icons';
import { api } from '@/api/client';
import type { ApiConfig, ModuleName } from '@/types';
import {
  MODEL_PRESETS,
  TRANSLATE_LANGUAGES,
  TRANSLATE_SOURCE_AUTO,
  languageName,
} from './configForms/constants';

const { TextArea } = Input;

export default function Translate() {
  const [configs, setConfigs] = useState<ApiConfig[]>([]);
  const [configId, setConfigId] = useState<number | ''>('');
  const [text, setText] = useState('');
  const [source, setSource] = useState<string>(TRANSLATE_SOURCE_AUTO.code);
  const [target, setTarget] = useState<string>('en');
  // Per-call model override. `null` means "use the config row's model";
  // an empty string would be sent to the backend, which would also fall
  // back — but we keep the convention that an absent value == default.
  const [model, setModel] = useState<string | null>(null);
  const [result, setResult] = useState<string>('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [meta, setMeta] = useState<{
    model: string;
    duration_ms: number;
    detected_source?: string;
  } | null>(null);
  const [messageApi, contextHolder] = message.useMessage();

  // Load configs and pre-pick the enabled translate one.
  useEffect(() => {
    api.listConfigs()
      .then((rows) => {
        setConfigs(rows);
        const enabled = rows.find((r) => r.module === ('translate' as ModuleName) && r.enabled);
        if (enabled) setConfigId(enabled.id);
      })
      .catch((e) => setError(String(e?.message ?? e)));
  }, []);

  // When the user switches configs, reset the per-call model override so it
  // tracks the new config's default. Keeps the dropdown from showing a stale
  // value that no longer applies.
  useEffect(() => {
    setModel(null);
  }, [configId]);

  // When user switches to a translate config that we haven't pre-filled, keep
  // the existing choice so we don't fight manual selection.
  const translateConfigs = useMemo(
    () => configs.filter((c) => c.module === ('translate' as ModuleName)),
    [configs],
  );
  const currentConfig = useMemo(
    () => configs.find((c) => c.id === configId),
    [configs, configId],
  );
  const hasKey = !!currentConfig?.has_api_key;

  const onSwap = () => {
    if (source === TRANSLATE_SOURCE_AUTO.code) {
      // Can't "swap to auto" — just keep the target and reset source to auto.
      setSource(target);
    } else {
      setSource(target);
      setTarget(source === TRANSLATE_SOURCE_AUTO.code ? 'en' : source);
    }
    // Also swap the result back into the input so the user can iterate.
    if (result) {
      setText(result);
      setResult('');
      setMeta(null);
    }
  };

  const onTranslate = async () => {
    const trimmed = text.trim();
    if (!trimmed) {
      setError('Source text is required');
      return;
    }
    if (!target) {
      setError('Target language is required');
      return;
    }
    if (source !== TRANSLATE_SOURCE_AUTO.code && source === target) {
      setError('Source and target languages are the same');
      return;
    }
    setBusy(true);
    setError(null);
    setResult('');
    setMeta(null);
    try {
      const r = await api.translate({
        text: trimmed,
        source,
        target,
        config_id: configId || undefined,
        // Only send `model` when the user actually picked / typed one. An
        // empty string would still travel as "" and be ignored by the
        // backend, but staying strict keeps the wire shape clean.
        model: model && model.trim() ? model.trim() : undefined,
      });
      setResult(r.translated_text);
      setMeta({
        model: r.model,
        duration_ms: r.duration_ms,
        detected_source: r.detected_source,
      });
    } catch (e: any) {
      setError(e?.body?.detail ?? e?.message ?? String(e));
    } finally {
      setBusy(false);
    }
  };

  const onClear = () => {
    setText('');
    setResult('');
    setMeta(null);
    setError(null);
  };

  const onCopy = async () => {
    if (!result) return;
    try {
      await navigator.clipboard.writeText(result);
      messageApi.success('Copied to clipboard');
    } catch {
      messageApi.error('Copy failed');
    }
  };

  // Ctrl/Cmd + Enter to send.
  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
      e.preventDefault();
      onTranslate();
    }
  };

  return (
    <>
      {contextHolder}
      <div className="page-title">
        <div>
          <h2>🌐 Translate</h2>
          <div className="page-sub">
            Bidirectional translation powered by the MiniMax chat model configured under{' '}
            <b>Config Center → Translate</b>. Results are returned as plain text — no
            explanations, no quotation marks. Tip: <kbd>⌘ / Ctrl + Enter</kbd> to translate.
          </div>
        </div>
      </div>

      {!hasKey && (
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 16 }}
          message="No API key configured"
          description={
            <>
              Open <b>Config Center → Translate</b> and paste your MiniMax API key, then come back here.
            </>
          }
        />
      )}

      <Card style={{ marginBottom: 16 }} bodyStyle={{ padding: 16 }}>
        <Space wrap size={12} align="center">
          <div>
            <div style={{ fontSize: 12, color: 'rgba(0,0,0,0.45)', marginBottom: 4 }}>Source</div>
            <Select
              value={source}
              onChange={setSource}
              style={{ width: 180 }}
              options={[
                { value: TRANSLATE_SOURCE_AUTO.code, label: TRANSLATE_SOURCE_AUTO.name },
                ...TRANSLATE_LANGUAGES.map((l) => ({ value: l.code, label: l.name })),
              ]}
            />
          </div>
          <Tooltip title="Swap languages">
            <Button
              shape="circle"
              icon={<SwapOutlined />}
              onClick={onSwap}
              style={{ marginTop: 18 }}
            />
          </Tooltip>
          <div>
            <div style={{ fontSize: 12, color: 'rgba(0,0,0,0.45)', marginBottom: 4 }}>Target</div>
            <Select
              value={target}
              onChange={setTarget}
              style={{ width: 180 }}
              options={TRANSLATE_LANGUAGES.map((l) => ({ value: l.code, label: l.name }))}
            />
          </div>

          <div>
            <div style={{ fontSize: 12, color: 'rgba(0,0,0,0.45)', marginBottom: 4 }}>
              Model{' '}
              <Typography.Text type="secondary" style={{ fontSize: 11 }}>
                (default: {currentConfig?.model || '—'})
              </Typography.Text>
            </div>
            <AutoComplete
              value={model ?? ''}
              onChange={(v) => setModel(v || null)}
              placeholder={currentConfig?.model || 'MiniMax-M2'}
              style={{ width: 220 }}
              allowClear
              options={MODEL_PRESETS.translate.map((m) => ({ value: m, label: m }))}
              filterOption={(input, opt) =>
                (opt?.value as string).toLowerCase().includes(input.toLowerCase())
              }
            />
          </div>

          <div style={{ flex: 1 }} />

          <div>
            <div style={{ fontSize: 12, color: 'rgba(0,0,0,0.45)', marginBottom: 4 }}>Config</div>
            <Select
              value={configId || undefined}
              onChange={(v) => setConfigId(v)}
              placeholder="(default translate config)"
              style={{ width: 260 }}
              allowClear
              options={translateConfigs.map((c) => ({
                value: c.id,
                label: `${c.display_name} · ${c.model}${c.has_api_key ? ' 🔑' : ' (no key)'}`,
              }))}
            />
          </div>
        </Space>
      </Card>

      <div className="translate-pane">
        <Card
          title={
            <Space>
              <span>Source · {source === TRANSLATE_SOURCE_AUTO.code ? 'Auto-detect' : languageName(source)}</span>
              {meta?.detected_source && source === TRANSLATE_SOURCE_AUTO.code && (
                <Tag color="blue">detected: {languageName(meta.detected_source)}</Tag>
              )}
            </Space>
          }
          extra={
            <Space>
              <Button size="small" icon={<ClearOutlined />} onClick={onClear} disabled={!text}>
                Clear
              </Button>
              <Button
                size="small"
                type="primary"
                icon={<ThunderboltOutlined />}
                loading={busy}
                onClick={onTranslate}
                disabled={!text.trim() || !target}
              >
                Translate
              </Button>
            </Space>
          }
        >
          <div className="translate-textarea">
            <TextArea
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={onKeyDown}
              placeholder="Paste or type the text you want to translate…"
              autoSize={{ minRows: 10, maxRows: 20 }}
              bordered
            />
          </div>
          {error && (
            <Alert type="error" showIcon message={error} style={{ marginTop: 12 }} />
          )}
        </Card>

        <Card
          title={
            <Space>
              <span>Result · {languageName(target)}</span>
              {meta && (
                <Tag color="default">
                  {meta.model} · {meta.duration_ms}ms
                </Tag>
              )}
            </Space>
          }
          extra={
            <Tooltip title="Copy translation">
              <Button size="small" icon={<CopyOutlined />} onClick={onCopy} disabled={!result} />
            </Tooltip>
          }
        >
          <div className={'translate-result' + (result ? '' : ' empty')}>
            {busy
              ? 'Translating…'
              : result
                ? result
                : 'Nothing yet. Hit Translate to see the output here.'}
          </div>
        </Card>
      </div>
    </>
  );
}
