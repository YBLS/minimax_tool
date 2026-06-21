import { useEffect, useState } from 'react';
import {
  Alert,
  Button,
  Card,
  Col,
  Empty,
  Input,
  Row,
  Select,
  Space,
  Tag,
  Typography,
  App as AntdApp,
} from 'antd';
import {
  ReloadOutlined,
  ThunderboltOutlined,
  LoadingOutlined,
} from '@ant-design/icons';
import { api } from '@/api/client';
import type { ApiConfig, GenerateResult, ModuleName, OutputFile } from '@/types';
import { ImageParamsForm, readImageParams, writeImageParams, IMAGE_DEFAULTS } from './configForms/ImageForm';
import { VoiceParamsForm, readVoiceParams, writeVoiceParams, VOICE_DEFAULTS } from './configForms/VoiceForm';
import { MusicParamsForm, readMusicParams, writeMusicParams, MUSIC_DEFAULTS } from './configForms/MusicForm';
import {
  VideoParamsForm, readVideoParams, writeVideoParams, VIDEO_DEFAULTS,
} from './configForms/VideoForm';

interface Props {
  module: ModuleName;
}

const MODULE_TITLES: Record<ModuleName, { label: string; sub: string }> = {
  image:     { label: 'Image Studio',     sub: 'Text → Image generation. Pick a model and tune the per-call params.' },
  voice:     { label: 'Voice Studio',     sub: 'Text → Speech (TTS) generation. Pick a voice, tweak speed / volume / pitch.' },
  music:     { label: 'Music Studio',     sub: 'Text / lyrics → Music generation.' },
  video:     { label: 'Video Studio',     sub: 'Video generation: T2V (text-only), I2V (first frame), FL2V (first + last frame).' },
  translate: { label: 'Translate Studio', sub: 'See the Translate page in the sidebar.' },
};

const STATUS_COLOR: Record<string, string> = {
  success: 'success',
  failed: 'error',
  running: 'processing',
  pending: 'default',
};

export default function Studio({ module }: Props) {
  const { message } = AntdApp.useApp();
  const [prompt, setPrompt] = useState('');
  const [configs, setConfigs] = useState<ApiConfig[]>([]);
  const [configId, setConfigId] = useState<number | ''>('');
  const [result, setResult] = useState<GenerateResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.listConfigs().then(setConfigs).catch((e) => setError(String(e?.message ?? e)));
  }, []);

  // Pre-fill per-call params from the chosen config's default_params + reset result
  useEffect(() => {
    setResult(null);
    setError(null);
    const c = configs.find((c) => c.module === module);
    setConfigId(c?.id ?? '');
    const d = c?.default_params ?? {};
    if (module === 'image') setImageParams(readImageParams(d));
    if (module === 'voice') setVoiceParams(readVoiceParams(d));
    if (module === 'music') setMusicParams(readMusicParams(d));
    if (module === 'video') setVideoParams(readVideoParams(d));
    setPrompt('');
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [module, configs]);

  // Per-module call-time params
  const [imageParams, setImageParams] = useState(() => readImageParams(IMAGE_DEFAULTS as any));
  const [voiceParams, setVoiceParams] = useState(() => readVoiceParams(VOICE_DEFAULTS as any));
  const [musicParams, setMusicParams] = useState(() => readMusicParams(MUSIC_DEFAULTS as any));
  const [videoParams, setVideoParams] = useState(() => readVideoParams({}));

  useEffect(() => {
    if (configs.length === 0) return;
    const c = configs.find((c) => c.module === module);
    const d = c?.default_params ?? {};
    if (module === 'image') setImageParams(readImageParams(d));
    if (module === 'voice') setVoiceParams(readVoiceParams(d));
    if (module === 'music') setMusicParams(readMusicParams(d));
    if (module === 'video') setVideoParams(readVideoParams(d));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [configs]);

  const resetParamsToConfigDefaults = () => {
    const c = configs.find((c) => c.module === module);
    const d = c?.default_params ?? {};
    if (module === 'image') setImageParams(readImageParams(d));
    if (module === 'voice') setVoiceParams(readVoiceParams(d));
    if (module === 'music') setMusicParams(readMusicParams(d));
    if (module === 'video') setVideoParams(readVideoParams(d));
    message.success('Reset to config defaults');
  };

  const onGenerate = async () => {
    if (!prompt.trim()) {
      setError('Prompt is required');
      return;
    }
    let params: Record<string, any> = {};
    if (module === 'image') params = writeImageParams(imageParams);
    if (module === 'voice') params = writeVoiceParams(voiceParams);
    if (module === 'music') params = writeMusicParams(musicParams);
    if (module === 'video') params = writeVideoParams(videoParams);

    setBusy(true);
    setError(null);
    try {
      const r = await api.generate(module, { prompt, params, config_id: configId || undefined });
      setResult(r);
      if (r.status === 'success') message.success('Done');
    } catch (e: any) {
      setError(e?.body?.detail ?? e?.message ?? String(e));
    } finally {
      setBusy(false);
    }
  };

  // Sub-mode guardrails (per-submode required fields)
  const missingFields: string[] = [];
  if (module === 'video') {
    if (!prompt.trim()) missingFields.push('Prompt');
    if ((videoParams.submode === 'i2v' || videoParams.submode === 'fl2v') && !videoParams.first_frame_image) {
      missingFields.push('First frame image');
    }
    if (videoParams.submode === 'fl2v' && !videoParams.last_frame_image) {
      missingFields.push('Last frame image');
    }
  }

  const title = MODULE_TITLES[module];

  return (
    <>
      <div className="page-title">
        <div>
          <h2>{title.label}</h2>
          <div className="page-sub">{title.sub}</div>
        </div>
      </div>

      <Row gutter={16}>
        <Col xs={24} lg={12}>
          <Card title="Inputs">
            <Space direction="vertical" size={12} style={{ width: '100%' }}>
              <div>
                <Typography.Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
                  Prompt · ⌘ / Ctrl + Enter to send
                </Typography.Text>
                <Input.TextArea
                  placeholder={`Describe the ${module} you want to generate…`}
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  onKeyDown={(e) => {
                    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') onGenerate();
                  }}
                  autoSize={{ minRows: 4, maxRows: 12 }}
                />
              </div>

              <div>
                <Typography.Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
                  Config
                </Typography.Text>
                <Select
                  value={configId === '' ? undefined : configId}
                  onChange={(v) => setConfigId(v ?? '')}
                  placeholder="(default for module)"
                  style={{ width: '100%' }}
                  allowClear
                  options={configs.filter((c) => c.module === module).map((c) => ({
                    value: c.id,
                    label: `${c.display_name} · ${c.has_api_key ? '🔑' : '(no key)'}`,
                  }))}
                />
              </div>

              <div>
                <Typography.Text
                  type="secondary"
                  style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: 1, display: 'block', margin: '4px 0 8px' }}
                >
                  Parameters
                </Typography.Text>
                {module === 'image' && <ImageParamsForm value={imageParams} onChange={setImageParams} />}
                {module === 'voice' && <VoiceParamsForm value={voiceParams} onChange={setVoiceParams} />}
                {module === 'music' && <MusicParamsForm value={musicParams} onChange={setMusicParams} />}
                {module === 'video' && <VideoParamsForm value={videoParams} onChange={setVideoParams} />}
              </div>

              <Space>
                <Button icon={<ReloadOutlined />} onClick={resetParamsToConfigDefaults}>
                  Use config defaults
                </Button>
                {result && (
                  <>
                    <Tag color={STATUS_COLOR[result.status] ?? 'default'}>{result.status}</Tag>
                    {result.duration_ms > 0 && <Tag>{result.duration_ms}ms</Tag>}
                  </>
                )}
              </Space>

              <Space>
                <Button
                  type="primary"
                  icon={busy ? <LoadingOutlined /> : <ThunderboltOutlined />}
                  onClick={onGenerate}
                  loading={busy}
                  disabled={!prompt.trim() || missingFields.length > 0}
                >
                  {busy ? 'Generating…' : `Generate ${title.label.split(' ')[0]}`}
                </Button>
                {missingFields.length > 0 && (
                  <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                    Missing: {missingFields.join(', ')}
                  </Typography.Text>
                )}
              </Space>

              {error && <Alert type="error" showIcon message={error} closable onClose={() => setError(null)} />}
            </Space>
          </Card>
        </Col>

        <Col xs={24} lg={12}>
          <Card title="Result">
            {!result && (
              <Empty description="Nothing yet. Hit Generate to see output here." style={{ padding: 32 }} />
            )}
            {result && result.error_message && (
              <pre className="json-block" style={{ color: '#f87171' }}>{result.error_message}</pre>
            )}
            {result && result.status === 'success' && result.output_files.length === 0 && (
              <Empty description="Empty result. Check request/response payloads in History." />
            )}
            {result && result.output_files.length > 0 && (
              <div className="media-grid" style={{ marginTop: 0 }}>
                {result.output_files.map((f, i) => <MediaTile key={i} file={f} />)}
              </div>
            )}
          </Card>
        </Col>
      </Row>
    </>
  );
}

function MediaTile({ file }: { file: OutputFile }) {
  const name = file.path ? file.path.split('/').pop() : '';
  const isImg = file.type === 'image' || (file.mime_type || '').startsWith('image/');
  const isVid = file.type === 'video' || (file.mime_type || '').startsWith('video/');
  const isAud = file.type === 'audio' || (file.mime_type || '').startsWith('audio/');

  return (
    <div className="media-card">
      {isImg && <img src={file.url} alt={name} />}
      {isVid && <video src={file.url} controls />}
      {isAud && <div style={{ padding: 24 }}><audio src={file.url} controls style={{ width: '100%' }} /></div>}
      <div className="meta">
        <span>{name}</span>
        <span>{file.size ? `${(file.size / 1024).toFixed(1)} KB` : ''}</span>
      </div>
    </div>
  );
}

// (No leftover cleanup needed.)
