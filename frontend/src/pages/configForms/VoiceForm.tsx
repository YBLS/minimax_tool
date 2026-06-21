// Voice / TTS params — POST /v1/t2a_v2
// voice_setting: { voice_id, speed, vol, pitch }
// audio_setting: { sample_rate, bitrate, format, channel }
// https://platform.minimaxi.com/document/T2A%20V2

import { Form, Input, Select, Slider, Space, Typography } from 'antd';
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

function ParamSlider({
  label, min, max, step, value, onChange, format,
}: {
  label: string;
  min: number;
  max: number;
  step: number;
  value: number;
  onChange: (n: number) => void;
  format?: (n: number) => string;
}) {
  return (
    <Form.Item
      label={
        <Space>
          {label}
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            · {format ? format(value) : value}
          </Typography.Text>
        </Space>
      }
    >
      <Slider min={min} max={max} step={step} value={value} onChange={onChange} />
    </Form.Item>
  );
}

export function VoiceParamsForm({ value, onChange }: Props) {
  const set = (patch: Partial<VoiceParams>) => onChange({ ...value, ...patch });
  const knownVoice = VOICE_PRESETS.find((v) => v.id === value.voice_id);

  return (
    <Space direction="vertical" size={12} style={{ width: '100%' }}>
      <Form.Item label="Voice">
        <Select
          value={knownVoice ? value.voice_id : '__custom__'}
          onChange={(v) => {
            if (v === '__custom__') return;
            set({ voice_id: v });
          }}
          options={[
            ...VOICE_PRESETS.map((v) => ({ value: v.id, label: `${v.label} · ${v.lang}` })),
            { value: '__custom__', label: 'Custom voice_id…' },
          ]}
          style={{ width: '100%' }}
        />
        {knownVoice
          ? <div className="field-hint"><b>{knownVoice.label}</b> · {knownVoice.lang}</div>
          : <Input
              style={{ marginTop: 8 }}
              value={value.voice_id}
              placeholder="Enter custom voice_id (e.g. male-qn-jingying)"
              onChange={(e) => set({ voice_id: e.target.value })}
            />
        }
      </Form.Item>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <ParamSlider label="Speed"  min={0.5} max={2.0} step={0.05} value={value.speed} onChange={(n) => set({ speed: n })} format={(n) => `${n.toFixed(2)}×`} />
        <ParamSlider label="Volume" min={0}   max={10}  step={0.1}  value={value.vol}   onChange={(n) => set({ vol: n })}   format={(n) => n.toFixed(1)} />
        <ParamSlider label="Pitch"  min={-12} max={12}  step={1}    value={value.pitch} onChange={(n) => set({ pitch: n })} format={(n) => (n > 0 ? `+${n}` : `${n}`) + ' semitone'} />
        <Form.Item label="Channel">
          <Select
            value={value.channel}
            onChange={(v) => set({ channel: v as 1 | 2 })}
            options={CHANNELS.map((c) => ({ value: c, label: `${c} (${c === 1 ? 'mono' : 'stereo'})` }))}
            style={{ width: '100%' }}
          />
        </Form.Item>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12 }}>
        <Form.Item label="Sample rate (Hz)">
          <Select
            value={value.sample_rate}
            onChange={(v) => set({ sample_rate: v })}
            options={SAMPLE_RATES.map((r) => ({ value: r, label: String(r) }))}
            style={{ width: '100%' }}
          />
        </Form.Item>
        <Form.Item label="Bitrate (bps)">
          <Select
            value={value.bitrate}
            onChange={(v) => set({ bitrate: v })}
            options={BITRATES.map((r) => ({ value: r, label: String(r) }))}
            style={{ width: '100%' }}
          />
        </Form.Item>
        <Form.Item label="Format">
          <Select
            value={value.format}
            onChange={(v) => set({ format: v as VoiceParams['format'] })}
            options={AUDIO_FORMATS.map((f) => ({ value: f, label: f }))}
            style={{ width: '100%' }}
          />
        </Form.Item>
      </div>
    </Space>
  );
}
