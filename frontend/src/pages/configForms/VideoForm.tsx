// Video params — POST /v1/video_generation
//
// Three sub-modes share the same endpoint. They differ in which fields are
// required / available:
//
//   T2V   — text-only. Required: model, prompt.
//           Models: MiniMax-Hailuo-2.3, MiniMax-Hailuo-2.3-Fast, MiniMax-Hailuo-02,
//                   T2V-01-Director, T2V-01.
//
//   I2V   — first-frame image + text. Required: model, first_frame_image.
//           Models: + I2V-01-Director, I2V-01-live, I2V-01.
//           first_frame_image: URL or `data:image/...;base64,...` (<20MB).
//
//   FL2V  — first + last frame. Required: model, first_frame_image, last_frame_image.
//           Models: MiniMax-Hailuo-02 only. No 512P. No fast_pretreatment.
//
// Common optional fields: duration (6|10), resolution (512P|720P|768P|1080P),
// prompt_optimizer (bool), fast_pretreatment (bool, T2V/I2V only),
// aigc_watermark (bool), callback_url (string).
//
// Available resolutions depend on the chosen model — see MODEL_RESOLUTIONS.
//

import { useMemo, useState } from 'react';
import { Button, Checkbox, Form, Input, Segmented, Select, Space, Typography } from 'antd';
import { ClearOutlined } from '@ant-design/icons';

// --- Sub-mode / model catalogues (from the official MiniMax docs, 2025-12) ---

export type VideoSubmode = 't2v' | 'i2v' | 'fl2v';

export const VIDEO_SUBMODES: { id: VideoSubmode; label: string; emoji: string; tagline: string }[] = [
  { id: 't2v',  label: 'T2V',  emoji: '✍️', tagline: 'Text → Video' },
  { id: 'i2v',  label: 'I2V',  emoji: '🖼', tagline: 'Image → Video (first frame)' },
  { id: 'fl2v', label: 'FL2V', emoji: '🎞', tagline: 'First + Last frame' },
];

const MODEL_SUBMODE_SUPPORT: Record<string, VideoSubmode[]> = {
  'MiniMax-Hailuo-2.3':    ['t2v', 'i2v'],
  'MiniMax-Hailuo-2.3-Fast': ['i2v'],
  'MiniMax-Hailuo-02':     ['t2v', 'i2v', 'fl2v'],
  'T2V-01-Director':       ['t2v'],
  'T2V-01':                ['t2v'],
  'I2V-01-Director':       ['i2v'],
  'I2V-01-live':           ['i2v'],
  'I2V-01':                ['i2v'],
};

export const ALL_VIDEO_MODELS = Object.keys(MODEL_SUBMODE_SUPPORT);

export function modelsForSubmode(submode: VideoSubmode): string[] {
  return ALL_VIDEO_MODELS.filter((m) => MODEL_SUBMODE_SUPPORT[m].includes(submode));
}

const RES_MATRIX: Record<string, Record<number, string[]>> = {
  'MiniMax-Hailuo-2.3':     { 6:  ['768P', '1080P'], 10: ['768P'] },
  'MiniMax-Hailuo-2.3-Fast':{ 6:  ['768P', '1080P'], 10: ['768P'] },
  'MiniMax-Hailuo-02':      { 6:  ['768P', '1080P'], 10: ['768P'] },
  '__I2V__MiniMax-Hailuo-02': { 6: ['512P', '768P', '1080P'], 10: ['512P', '768P'] },
  '__FL2V__MiniMax-Hailuo-02': { 6: ['768P', '1080P'], 10: ['768P'] },
  '__other__':              { 6:  ['720P', '1080P'], 10: [] },
};

export function resolutionsFor(model: string, submode: VideoSubmode, duration: number): string[] {
  if (model === 'MiniMax-Hailuo-02' && submode === 'i2v') {
    return RES_MATRIX['__I2V__MiniMax-Hailuo-02'][duration] ?? ['768P'];
  }
  if (model === 'MiniMax-Hailuo-02' && submode === 'fl2v') {
    return RES_MATRIX['__FL2V__MiniMax-Hailuo-02'][duration] ?? ['768P'];
  }
  if (model in RES_MATRIX) {
    return RES_MATRIX[model][duration] ?? [];
  }
  return RES_MATRIX['__other__'][duration] ?? ['720P'];
}

export function durationsFor(model: string, submode: VideoSubmode): number[] {
  if (model in RES_MATRIX || (model === 'MiniMax-Hailuo-02')) {
    return [6, 10];
  }
  return [6];
}

// --- Per-call params shape ---

export interface VideoParams {
  submode: VideoSubmode;
  model: string;
  first_frame_image: string;
  first_frame_image_filename: string;
  last_frame_image: string;
  last_frame_image_filename: string;
  duration: number;
  resolution: string;
  prompt_optimizer: boolean;
  fast_pretreatment: boolean;
  aigc_watermark: boolean;
  callback_url: string;
}

export const VIDEO_DEFAULTS: VideoParams = {
  submode: 't2v',
  model: 'MiniMax-Hailuo-02',
  first_frame_image: '',
  first_frame_image_filename: '',
  last_frame_image: '',
  last_frame_image_filename: '',
  duration: 6,
  resolution: '768P',
  prompt_optimizer: true,
  fast_pretreatment: false,
  aigc_watermark: false,
  callback_url: '',
};

export function readVideoParams(d: Record<string, any> = {}): VideoParams {
  const out: VideoParams = { ...VIDEO_DEFAULTS, ...d };
  out.duration = Number(out.duration) || VIDEO_DEFAULTS.duration;
  out.prompt_optimizer = Boolean(out.prompt_optimizer);
  out.fast_pretreatment = Boolean(out.fast_pretreatment);
  out.aigc_watermark = Boolean(out.aigc_watermark);
  return out;
}

export function writeVideoParams(p: VideoParams): Record<string, any> {
  const out: Record<string, any> = {
    submode: p.submode,
    model: p.model,
    duration: p.duration,
    resolution: p.resolution,
    prompt_optimizer: p.prompt_optimizer,
    aigc_watermark: p.aigc_watermark,
  };
  if (p.submode === 'i2v' || p.submode === 'fl2v') {
    if (p.first_frame_image) out.first_frame_image = p.first_frame_image;
  }
  if (p.submode === 'fl2v') {
    if (p.last_frame_image) out.last_frame_image = p.last_frame_image;
  }
  if (p.submode !== 'fl2v') {
    out.fast_pretreatment = p.fast_pretreatment;
  }
  if (p.callback_url) out.callback_url = p.callback_url;
  return out;
}

function readFileAsDataURL(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const fr = new FileReader();
    fr.onload = () => resolve(String(fr.result || ''));
    fr.onerror = () => reject(fr.error || new Error('FileReader failed'));
    fr.readAsDataURL(file);
  });
}

interface ImageFieldProps {
  label: string;
  value: string;
  filename: string;
  onChange: (dataUrl: string, filename: string) => void;
}

function ImageField({ label, value, filename, onChange }: ImageFieldProps) {
  const [mode, setMode] = useState<'url' | 'upload'>(value.startsWith('data:') ? 'upload' : 'url');
  const [dragOver, setDragOver] = useState(false);

  const onFile = async (f: File | undefined) => {
    if (!f) return;
    if (f.size > 20 * 1024 * 1024) {
      // antd Modal would be nicer but inline keeps the page compact.
      alert(`File too big: ${(f.size / 1024 / 1024).toFixed(1)} MB (limit 20 MB)`);
      return;
    }
    const dataUrl = await readFileAsDataURL(f);
    onChange(dataUrl, f.name);
  };

  return (
    <Form.Item label={label}>
      <Space style={{ marginBottom: 6 }}>
        <Button
          size="small"
          type={mode === 'url' ? 'primary' : 'default'}
          onClick={() => { setMode('url'); if (!value || value.startsWith('data:')) onChange('', ''); }}
        >URL</Button>
        <Button
          size="small"
          type={mode === 'upload' ? 'primary' : 'default'}
          onClick={() => setMode('upload')}
        >Upload</Button>
        {value && (
          <Button
            size="small"
            type="text"
            icon={<ClearOutlined />}
            onClick={() => onChange('', '')}
            title="Clear"
          />
        )}
      </Space>
      {mode === 'url' && (
        <Input
          value={value.startsWith('data:') ? '' : value}
          placeholder="https://cdn.example.com/your-image.jpg"
          onChange={(e) => onChange(e.target.value, filename)}
        />
      )}
      {mode === 'upload' && (
        <div
          className={'dropzone' + (dragOver ? ' over' : '')}
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault(); setDragOver(false);
            const f = e.dataTransfer.files?.[0];
            onFile(f);
          }}
        >
          <input
            type="file"
            accept="image/jpeg,image/jpg,image/png,image/webp"
            onChange={(e) => onFile(e.target.files?.[0] ?? undefined)}
          />
          {filename
            ? <div className="dropzone-info">📎 {filename} <Typography.Text type="secondary">({Math.round((value.length * 3) / 4 / 1024)} KB base64)</Typography.Text></div>
            : <div className="dropzone-info"><Typography.Text type="secondary">Drop a JPG/PNG/WebP (≤20 MB) or click to pick</Typography.Text></div>}
        </div>
      )}
    </Form.Item>
  );
}

interface Props {
  value: VideoParams;
  onChange: (next: VideoParams) => void;
}

export function VideoParamsForm({ value, onChange }: Props) {
  const set = (patch: Partial<VideoParams>) => onChange({ ...value, ...patch });

  const onSubmodeChange = (submode: VideoSubmode) => {
    const valid = modelsForSubmode(submode);
    const newModel = valid.includes(value.model) ? value.model : (valid[0] ?? value.model);
    const durations = durationsFor(newModel, submode);
    const newDuration = durations.includes(value.duration) ? value.duration : (durations[0] ?? 6);
    const resolutions = resolutionsFor(newModel, submode, newDuration);
    const newResolution = resolutions.includes(value.resolution) ? value.resolution : (resolutions[0] ?? '768P');
    onChange({
      ...value,
      submode,
      model: newModel,
      duration: newDuration,
      resolution: newResolution,
      first_frame_image: submode === 't2v' ? '' : value.first_frame_image,
      first_frame_image_filename: submode === 't2v' ? '' : value.first_frame_image_filename,
      last_frame_image: submode === 'fl2v' ? value.last_frame_image : '',
      last_frame_image_filename: submode === 'fl2v' ? value.last_frame_image_filename : '',
    });
  };

  const onModelChange = (model: string) => {
    const durations = durationsFor(model, value.submode);
    const newDuration = durations.includes(value.duration) ? value.duration : (durations[0] ?? 6);
    const resolutions = resolutionsFor(model, value.submode, newDuration);
    const newResolution = resolutions.includes(value.resolution) ? value.resolution : (resolutions[0] ?? '768P');
    onChange({ ...value, model, duration: newDuration, resolution: newResolution });
  };

  const onDurationChange = (duration: number) => {
    const resolutions = resolutionsFor(value.model, value.submode, duration);
    const newResolution = resolutions.includes(value.resolution) ? value.resolution : (resolutions[0] ?? '768P');
    onChange({ ...value, duration, resolution: newResolution });
  };

  const availableModels = useMemo(() => modelsForSubmode(value.submode), [value.submode]);
  const availableDurations = useMemo(() => durationsFor(value.model, value.submode), [value.model, value.submode]);
  const availableResolutions = useMemo(
    () => resolutionsFor(value.model, value.submode, value.duration),
    [value.model, value.submode, value.duration],
  );

  return (
    <Space direction="vertical" size={12} style={{ width: '100%' }}>
      <Form.Item label="Sub-mode">
        <Segmented
          value={value.submode}
          onChange={(v) => onSubmodeChange(v as VideoSubmode)}
          options={VIDEO_SUBMODES.map((s) => ({ value: s.id, label: `${s.emoji} ${s.label}` }))}
          block
        />
        <div className="field-hint">
          {VIDEO_SUBMODES.find((s) => s.id === value.submode)?.tagline}
        </div>
      </Form.Item>

      <Form.Item label="Model">
        <Select
          value={value.model}
          onChange={onModelChange}
          options={availableModels.map((m) => ({ value: m, label: m }))}
          style={{ width: '100%' }}
        />
        <div className="field-hint">
          {value.model === 'MiniMax-Hailuo-02' && value.submode === 'fl2v' && 'FL2V only works with Hailuo-02 (no 512P, no fast_pretreatment).'}
          {value.model === 'MiniMax-Hailuo-2.3' && 'Latest flagship (10.28 release, Oct 2025).'}
        </div>
      </Form.Item>

      {(value.submode === 'i2v' || value.submode === 'fl2v') && (
        <ImageField
          label="First frame image"
          value={value.first_frame_image}
          filename={value.first_frame_image_filename}
          onChange={(url, fn) => set({ first_frame_image: url, first_frame_image_filename: fn })}
        />
      )}
      {value.submode === 'fl2v' && (
        <ImageField
          label="Last frame image"
          value={value.last_frame_image}
          filename={value.last_frame_image_filename}
          onChange={(url, fn) => set({ last_frame_image: url, last_frame_image_filename: fn })}
        />
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <Form.Item label="Duration">
          <Select
            value={value.duration}
            onChange={onDurationChange}
            options={availableDurations.map((d) => ({ value: d, label: `${d}s` }))}
            style={{ width: '100%' }}
          />
        </Form.Item>
        <Form.Item label="Resolution">
          <Select
            value={value.resolution}
            onChange={(v) => set({ resolution: v })}
            options={availableResolutions.map((r) => ({ value: r, label: r }))}
            style={{ width: '100%' }}
          />
          {availableResolutions.length === 0 && (
            <div className="field-hint">No resolution for this combo.</div>
          )}
        </Form.Item>
      </div>

      <Space size={24} wrap>
        <Checkbox
          checked={value.prompt_optimizer}
          onChange={(e) => set({ prompt_optimizer: e.target.checked })}
        >
          Optimize prompt automatically
        </Checkbox>
        {value.submode !== 'fl2v' && (
          <Checkbox
            checked={value.fast_pretreatment}
            onChange={(e) => set({ fast_pretreatment: e.target.checked })}
          >
            Fast pretreatment <Typography.Text type="secondary">(faster optimization)</Typography.Text>
          </Checkbox>
        )}
        <Checkbox
          checked={value.aigc_watermark}
          onChange={(e) => set({ aigc_watermark: e.target.checked })}
        >
          Add AIGC watermark
        </Checkbox>
      </Space>

      <Form.Item
        label={
          <Space>
            Callback URL
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>· optional, for server-side status push</Typography.Text>
          </Space>
        }
      >
        <Input
          value={value.callback_url}
          placeholder="https://your-server.com/webhook"
          onChange={(e) => set({ callback_url: e.target.value })}
        />
      </Form.Item>
    </Space>
  );
}
