// Music params — POST /v1/music_generation
// body: { model, prompt, lyrics, audio_setting: { sample_rate, bitrate, format } }
//
// Note (2025-12): music-2.0 (current flagship) REQUIRES the `lyrics` field
// — submitting an empty string returns base_resp.code=2013. Use the
// `[Instrumental]` section marker for instrumental tracks.

import { Form, Input, Select, Space, Typography } from 'antd';
import { AUDIO_FORMATS, BITRATES, SAMPLE_RATES } from './constants';

export interface MusicParams {
  lyrics: string;
  sample_rate: number;
  bitrate: number;
  format: 'mp3' | 'pcm' | 'wav' | 'flac';
}

export const MUSIC_DEFAULTS: MusicParams = {
  lyrics: '[Instrumental]',
  sample_rate: 32000,
  bitrate: 128000,
  format: 'mp3',
};

export function readMusicParams(d: Record<string, any> = {}): MusicParams {
  return {
    lyrics: d.lyrics ?? MUSIC_DEFAULTS.lyrics,
    sample_rate: Number(d.sample_rate) || MUSIC_DEFAULTS.sample_rate,
    bitrate: Number(d.bitrate) || MUSIC_DEFAULTS.bitrate,
    format: d.format ?? MUSIC_DEFAULTS.format,
  };
}

export function writeMusicParams(p: MusicParams): Record<string, any> {
  return { ...p };
}

interface Props {
  value: MusicParams;
  onChange: (next: MusicParams) => void;
}

export function MusicParamsForm({ value, onChange }: Props) {
  const set = (patch: Partial<MusicParams>) => onChange({ ...value, ...patch });

  return (
    <Space direction="vertical" size={12} style={{ width: '100%' }}>
      <Form.Item
        label={
          <Space>
            Lyrics
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              · required by music-2.0
            </Typography.Text>
          </Space>
        }
      >
        <Input.TextArea
          value={value.lyrics}
          onChange={(e) => set({ lyrics: e.target.value })}
          placeholder="[Verse]&#10;月光洒在旧屋檐&#10;..."
          autoSize={{ minRows: 4, maxRows: 10 }}
        />
        <div className="field-hint">
          music-2.0 必须填 lyrics；纯器乐用 <code>[Instrumental]</code> 占位。可用
          <code>[Verse]</code> / <code>[Chorus]</code> 等段落标记。
        </div>
      </Form.Item>

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
            onChange={(v) => set({ format: v as MusicParams['format'] })}
            options={AUDIO_FORMATS.map((f) => ({ value: f, label: f }))}
            style={{ width: '100%' }}
          />
        </Form.Item>
      </div>
    </Space>
  );
}
