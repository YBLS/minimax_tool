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
// `?`/inconclusive combinations (e.g. Hailuo-02 1080P+10s) are filtered out
// by excluding the offending option when the related constraint is set.

import { useMemo, useState } from 'react';

// --- Sub-mode / model catalogues (from the official MiniMax docs, 2025-12) ---

export type VideoSubmode = 't2v' | 'i2v' | 'fl2v';

export const VIDEO_SUBMODES: { id: VideoSubmode; label: string; emoji: string; tagline: string }[] = [
  { id: 't2v',  label: 'T2V',  emoji: '✍️', tagline: 'Text → Video' },
  { id: 'i2v',  label: 'I2V',  emoji: '🖼', tagline: 'Image → Video (first frame)' },
  { id: 'fl2v', label: 'FL2V', emoji: '🎞', tagline: 'First + Last frame' },
];

// (model, submode) → true if the model supports the submode
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

// (model, duration) → list of available resolutions.
// Encodes the official matrix:
//
//   | Model                    | 6s 720P | 6s 768P | 6s 1080P | 10s 768P | 10s 1080P |
//   | MiniMax-Hailuo-2.3       |         |    ✓   |     ✓    |     ✓   |           |
//   | MiniMax-Hailuo-2.3-Fast  |         |    ✓   |     ✓    |     ✓   |           |
//   | MiniMax-Hailuo-02 (T2V)  |         |    ✓   |     ✓    |     ✓   |           |
//   | MiniMax-Hailuo-02 (I2V)  |         |  512P  |  768P    |  1080P  |           |
//   | MiniMax-Hailuo-02 (FL2V) |         |  768P  |  1080P   |   768P  |           |
//   | other T2V/I2V            |    ✓   |        |     ✓    |         |           |
const RES_MATRIX: Record<string, Record<number, string[]>> = {
  'MiniMax-Hailuo-2.3':     { 6:  ['768P', '1080P'], 10: ['768P'] },
  'MiniMax-Hailuo-2.3-Fast':{ 6:  ['768P', '1080P'], 10: ['768P'] },
  'MiniMax-Hailuo-02':      { 6:  ['768P', '1080P'], 10: ['768P'] },
  // I2V extra: 512P (FL2V doesn't have 512P — handled below)
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
  // Most flagships support both 6s and 10s; older T2V/I2V are 6s only.
  if (model in RES_MATRIX || (model === 'MiniMax-Hailuo-02')) {
    return [6, 10];
  }
  return [6];
}

// --- Per-call params shape ---

export interface VideoParams {
  submode: VideoSubmode;
  model: string;
  // Image fields — only I2V / FL2V use them
  first_frame_image: string;   // '' = unset
  first_frame_image_filename: string;  // for display
  last_frame_image: string;
  last_frame_image_filename: string;
  // Common
  duration: number;
  resolution: string;
  prompt_optimizer: boolean;
  fast_pretreatment: boolean;  // not for FL2V
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
  // Drop empty image fields and empty callback_url so _drop_unset on the
  // server side actually removes them (T2V shouldn't send first_frame_image).
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
  // fast_pretreatment: T2V / I2V only, FL2V ignores
  if (p.submode !== 'fl2v') {
    out.fast_pretreatment = p.fast_pretreatment;
  }
  if (p.callback_url) out.callback_url = p.callback_url;
  return out;
}

// --- File → base64 data URL helper ---

function readFileAsDataURL(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const fr = new FileReader();
    fr.onload = () => resolve(String(fr.result || ''));
    fr.onerror = () => reject(fr.error || new Error('FileReader failed'));
    fr.readAsDataURL(file);
  });
}

// --- Form component ---

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
      alert(`File too big: ${(f.size / 1024 / 1024).toFixed(1)} MB (limit 20 MB)`);
      return;
    }
    const dataUrl = await readFileAsDataURL(f);
    onChange(dataUrl, f.name);
  };

  return (
    <div className="field">
      <label>{label}</label>
      <div className="row" style={{ gap: 4, marginBottom: 6 }}>
        <button
          type="button"
          className={'tab-sm' + (mode === 'url' ? ' active' : '')}
          onClick={() => { setMode('url'); if (!value || value.startsWith('data:')) onChange('', ''); }}
        >URL</button>
        <button
          type="button"
          className={'tab-sm' + (mode === 'upload' ? ' active' : '')}
          onClick={() => { setMode('upload'); }}
        >Upload</button>
        {value && (
          <button type="button" className="ghost" onClick={() => onChange('', '')} title="Clear">✕</button>
        )}
      </div>
      {mode === 'url' && (
        <input
          type="text"
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
            ? <div className="dropzone-info">📎 {filename} <span className="muted">({Math.round((value.length * 3) / 4 / 1024)} KB base64)</span></div>
            : <div className="dropzone-info muted">Drop a JPG/PNG/WebP (≤20 MB) or click to pick</div>}
        </div>
      )}
    </div>
  );
}

interface Props {
  value: VideoParams;
  onChange: (next: VideoParams) => void;
}

export function VideoParamsForm({ value, onChange }: Props) {
  const set = (patch: Partial<VideoParams>) => onChange({ ...value, ...patch });

  // When submode changes: clamp the model to one that supports the new submode
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
      // Clear image fields that don't apply to the new submode
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
    [value.model, value.submode, value.duration]
  );

  return (
    <>
      <div className="field">
        <label>Sub-mode</label>
        <div className="segmented">
          {VIDEO_SUBMODES.map((s) => (
            <button
              key={s.id}
              type="button"
              className={'seg' + (s.id === value.submode ? ' active' : '')}
              onClick={() => onSubmodeChange(s.id)}
              title={s.tagline}
            >
              {s.emoji} {s.label}
            </button>
          ))}
        </div>
        <div className="hint">
          {VIDEO_SUBMODES.find((s) => s.id === value.submode)?.tagline}
        </div>
      </div>

      <div className="field">
        <label>Model</label>
        <select value={value.model} onChange={(e) => onModelChange(e.target.value)}>
          {availableModels.map((m) => <option key={m} value={m}>{m}</option>)}
        </select>
        <div className="hint muted">
          {value.model === 'MiniMax-Hailuo-02' && value.submode === 'fl2v' && 'FL2V only works with Hailuo-02 (no 512P, no fast_pretreatment).'}
          {value.model === 'MiniMax-Hailuo-2.3' && 'Latest flagship (10.28 release, Oct 2025).'}
        </div>
      </div>

      {(value.submode === 'i2v' || value.submode === 'fl2v') && (
        <ImageField
          label={value.submode === 'fl2v' ? 'First frame image' : 'First frame image'}
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

      <div className="grid-2">
        <div className="field">
          <label>Duration</label>
          <select value={value.duration} onChange={(e) => onDurationChange(Number(e.target.value))}>
            {availableDurations.map((d) => <option key={d} value={d}>{d}s</option>)}
          </select>
        </div>
        <div className="field">
          <label>Resolution</label>
          <select value={value.resolution} onChange={(e) => set({ resolution: e.target.value })}>
            {availableResolutions.map((r) => <option key={r} value={r}>{r}</option>)}
          </select>
          <div className="hint muted">
            {availableResolutions.length === 0 && 'No resolution for this combo.'}
          </div>
        </div>
      </div>

      <div className="grid-2">
        <div className="field" style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
          <input
            type="checkbox"
            id="prompt-optimizer"
            checked={value.prompt_optimizer}
            onChange={(e) => set({ prompt_optimizer: e.target.checked })}
            style={{ width: 'auto' }}
          />
          <label htmlFor="prompt-optimizer" style={{ margin: 0, textTransform: 'none', fontSize: 13, color: 'var(--text)' }}>
            Optimize prompt automatically
          </label>
        </div>
        {value.submode !== 'fl2v' && (
          <div className="field" style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
            <input
              type="checkbox"
              id="fast-pretreatment"
              checked={value.fast_pretreatment}
              onChange={(e) => set({ fast_pretreatment: e.target.checked })}
              style={{ width: 'auto' }}
            />
            <label htmlFor="fast-pretreatment" style={{ margin: 0, textTransform: 'none', fontSize: 13, color: 'var(--text)' }}>
              Fast pretreatment <span className="muted">(faster optimization)</span>
            </label>
          </div>
        )}
        <div className="field" style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
          <input
            type="checkbox"
            id="aigc-watermark"
            checked={value.aigc_watermark}
            onChange={(e) => set({ aigc_watermark: e.target.checked })}
            style={{ width: 'auto' }}
          />
          <label htmlFor="aigc-watermark" style={{ margin: 0, textTransform: 'none', fontSize: 13, color: 'var(--text)' }}>
            Add AIGC watermark
          </label>
        </div>
      </div>

      <div className="field">
        <label>Callback URL <span className="muted" style={{ textTransform: 'none' }}>· optional, for server-side status push</span></label>
        <input
          type="text"
          value={value.callback_url}
          placeholder="https://your-server.com/webhook"
          onChange={(e) => set({ callback_url: e.target.value })}
        />
      </div>
    </>
  );
}
