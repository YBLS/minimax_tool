// Voice / TTS params — POST /v1/t2a_v2
// voice_setting: { voice_id, speed, vol, pitch }
// audio_setting: { sample_rate, bitrate, format, channel }
// https://platform.minimaxi.com/document/T2A%20V2

import {
  AUDIO_FORMATS, BITRATES, CHANNELS, SAMPLE_RATES, VOICE_PRESETS, VOICE_ID_DEFAULT,
} from './constants';

export interface VoiceParams {
  voice_id: string;
  speed: number;
  vol: number;
  pitch: number;
  sample_rate: number;
  bitrate: number;
  format: 'mp3' | 'pcm' | 'wav' | 'flac';
  channel: 1 | 2;
}

export const VOICE_DEFAULTS: VoiceParams = {
  voice_id: VOICE_ID_DEFAULT,
  speed: 1.0,
  vol: 1.0,
  pitch: 0,
  sample_rate: 32000,
  bitrate: 128000,
  format: 'mp3',
  channel: 1,
};

export function readVoiceParams(d: Record<string, any> = {}): VoiceParams {
  const out: VoiceParams = { ...VOICE_DEFAULTS, ...d };
  // Coerce types
  out.speed = Number(out.speed) || VOICE_DEFAULTS.speed;
  out.vol   = Number(out.vol)   || VOICE_DEFAULTS.vol;
  out.pitch = Number(out.pitch) || VOICE_DEFAULTS.pitch;
  out.sample_rate = Number(out.sample_rate) || VOICE_DEFAULTS.sample_rate;
  out.bitrate     = Number(out.bitrate)     || VOICE_DEFAULTS.bitrate;
  out.channel     = (Number(out.channel) || 1) as 1 | 2;
  return out;
}

export function writeVoiceParams(p: VoiceParams): Record<string, any> {
  return { ...p };
}

interface Props {
  value: VoiceParams;
  onChange: (next: VoiceParams) => void;
}

function Slider({
  label, min, max, step, value, onChange, format,
}: { label: string; min: number; max: number; step: number; value: number; onChange: (n: number) => void; format?: (n: number) => string }) {
  return (
    <div className="field">
      <label>{label} <span className="muted" style={{ textTransform: 'none' }}>· {format ? format(value) : value}</span></label>
      <input
        type="range"
        min={min} max={max} step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
      />
    </div>
  );
}

export function VoiceParamsForm({ value, onChange }: Props) {
  const set = (patch: Partial<VoiceParams>) => onChange({ ...value, ...patch });
  const knownVoice = VOICE_PRESETS.find((v) => v.id === value.voice_id);

  return (
    <>
      <div className="field">
        <label>Voice</label>
        <select
          value={knownVoice ? value.voice_id : '__custom__'}
          onChange={(e) => {
            const v = e.target.value;
            if (v === '__custom__') {
              // keep current value, just flip into custom mode by no-op
              return;
            }
            set({ voice_id: v });
          }}
        >
          {VOICE_PRESETS.map((v) => (
            <option key={v.id} value={v.id}>{v.label} · {v.lang}</option>
          ))}
          <option value="__custom__">Custom voice_id…</option>
        </select>
        {knownVoice
          ? <div className="hint"><b>{knownVoice.label}</b> · {knownVoice.lang}</div>
          : <div className="field" style={{ marginTop: 8 }}>
              <input
                type="text"
                value={value.voice_id}
                placeholder="Enter custom voice_id (e.g. male-qn-jingying)"
                onChange={(e) => set({ voice_id: e.target.value })}
              />
              <div className="hint muted">Full list: <code>POST /v1/audio/minimax/voices/list</code></div>
            </div>
        }
      </div>

      <div className="grid-2">
        <Slider label="Speed"   min={0.5} max={2.0}  step={0.05} value={value.speed} onChange={(n) => set({ speed: n })} format={(n) => `${n.toFixed(2)}×`} />
        <Slider label="Volume"  min={0}   max={10}   step={0.1}  value={value.vol}   onChange={(n) => set({ vol: n })}   format={(n) => n.toFixed(1)} />
        <Slider label="Pitch"   min={-12} max={12}   step={1}    value={value.pitch} onChange={(n) => set({ pitch: n })} format={(n) => (n > 0 ? `+${n}` : `${n}`) + ' semitone'} />
        <div className="field">
          <label>Channel</label>
          <select value={value.channel} onChange={(e) => set({ channel: Number(e.target.value) as 1 | 2 })}>
            {CHANNELS.map((c) => <option key={c} value={c}>{c} ({c === 1 ? 'mono' : 'stereo'})</option>)}
          </select>
        </div>
      </div>

      <div className="grid-3">
        <div className="field">
          <label>Sample rate (Hz)</label>
          <select value={value.sample_rate} onChange={(e) => set({ sample_rate: Number(e.target.value) })}>
            {SAMPLE_RATES.map((r) => <option key={r} value={r}>{r}</option>)}
          </select>
        </div>
        <div className="field">
          <label>Bitrate (bps)</label>
          <select value={value.bitrate} onChange={(e) => set({ bitrate: Number(e.target.value) })}>
            {BITRATES.map((r) => <option key={r} value={r}>{r}</option>)}
          </select>
        </div>
        <div className="field">
          <label>Format</label>
          <select value={value.format} onChange={(e) => set({ format: e.target.value as any })}>
            {AUDIO_FORMATS.map((f) => <option key={f} value={f}>{f}</option>)}
          </select>
        </div>
      </div>
    </>
  );
}
