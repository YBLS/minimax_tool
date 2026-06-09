import { useEffect, useState } from 'react';
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

export default function Studio({ module }: Props) {
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

  // Per-module call-time params (initialized from defaults, re-init when configs load)
  const [imageParams, setImageParams] = useState(() => readImageParams(IMAGE_DEFAULTS as any));
  const [voiceParams, setVoiceParams] = useState(() => readVoiceParams(VOICE_DEFAULTS as any));
  const [musicParams, setMusicParams] = useState(() => readMusicParams(MUSIC_DEFAULTS as any));
  const [videoParams, setVideoParams] = useState(() => readVideoParams({}));

  // Initialise from default_params when configs first load
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
    if (module === 'video') {
      params = writeVideoParams(videoParams);
      // The user-typed prompt wins. The video submode carries its own `prompt`
      // in the params for the model field guide, but the API body uses {{prompt}}.
    }

    setBusy(true); setError(null);
    try {
      const r = await api.generate(module, { prompt, params, config_id: configId || undefined });
      setResult(r);
    } catch (e: any) {
      setError(e?.body?.detail ?? e?.message ?? String(e));
    } finally { setBusy(false); }
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

  const moduleLabel = {
    image: 'Image', voice: 'Voice', music: 'Music', video: 'Video',
  }[module];

  return (
    <>
      <div className="page-header">
        <div>
          <h2>{moduleLabel} Studio</h2>
          <div className="sub">
            {module === 'image' && 'Text → Image generation. Pick a model and tune the per-call params.'}
            {module === 'voice' && 'Text → Speech (TTS) generation. Pick a voice, tweak speed / volume / pitch.'}
            {module === 'music' && 'Text / lyrics → Music generation.'}
            {module === 'video' && 'Video generation: T2V (text-only), I2V (first frame), FL2V (first + last frame).'}
          </div>
        </div>
      </div>

      <div className="grid-2">
        <div className="card">
          <div className="field">
            <label>Prompt</label>
            <textarea
              placeholder={`Describe the ${module} you want to generate…`}
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              onKeyDown={(e) => { if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') onGenerate(); }}
            />
            <div className="hint">Tip: <span className="kbd">⌘ / Ctrl + Enter</span> to send</div>
          </div>

          <div className="field">
            <label>Config</label>
            <select value={configId} onChange={(e) => setConfigId(e.target.value ? Number(e.target.value) : '')}>
              <option value="">(default for module)</option>
              {configs.filter((c) => c.module === module).map((c) => (
                <option key={c.id} value={c.id}>
                  {c.display_name} {c.has_api_key ? '· 🔑' : '· (no key)'}
                </option>
              ))}
            </select>
          </div>

          <h4 className="muted" style={{ margin: '12px 0 8px', textTransform: 'uppercase', fontSize: 11, letterSpacing: 1 }}>
            Parameters
          </h4>

          {module === 'image' && <ImageParamsForm value={imageParams} onChange={setImageParams} />}
          {module === 'voice' && <VoiceParamsForm value={voiceParams} onChange={setVoiceParams} />}
          {module === 'music' && <MusicParamsForm value={musicParams} onChange={setMusicParams} />}
          {module === 'video' && <VideoParamsForm value={videoParams} onChange={setVideoParams} />}

          <div className="row" style={{ marginTop: 8 }}>
            <button className="ghost" onClick={resetParamsToConfigDefaults} title="Reset to the selected config's default_params">
              ↺ Use config defaults
            </button>
            <div className="spacer" />
            {result && <span className={'tag ' + result.status}>{result.status}</span>}
            {result && result.duration_ms > 0 && <span className="tag">{result.duration_ms}ms</span>}
          </div>

          <div className="row" style={{ marginTop: 12 }}>
            <button
              className="primary"
              onClick={onGenerate}
              disabled={busy || !prompt.trim() || missingFields.length > 0}
              title={missingFields.length > 0 ? `Missing: ${missingFields.join(', ')}` : ''}
            >
              {busy
                ? <><span className="spinner" />&nbsp;Generating…</>
                : `Generate ${moduleLabel}`}
            </button>
            {missingFields.length > 0 && (
              <span className="muted" style={{ fontSize: 12, marginLeft: 8 }}>
                Missing: {missingFields.join(', ')}
              </span>
            )}
          </div>

          {error && <div className="toast error" style={{ position: 'static', marginTop: 12 }}>{error}</div>}
        </div>

        <div className="card">
          <label>Result</label>
          {!result && <div className="empty">Nothing yet. Hit Generate to see output here.</div>}
          {result && result.error_message && (
            <pre className="json" style={{ color: 'var(--danger)' }}>{result.error_message}</pre>
          )}
          {result && result.output_files.length > 0 && (
            <div className="media-grid">
              {result.output_files.map((f, i) => <MediaTile key={i} file={f} />)}
            </div>
          )}
          {result && result.output_files.length === 0 && !result.error_message && (
            <div className="empty">Empty result. Check request/response payloads in History.</div>
          )}
        </div>
      </div>
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
