// Music params — POST /v1/music_generation
// body: { model, prompt, lyrics, audio_setting: { sample_rate, bitrate, format } }
//
// Note (2025-12): music-2.0 (current flagship) REQUIRES the `lyrics` field
// — submitting an empty string returns base_resp.code=2013. Use the
// `[Instrumental]` section marker for instrumental tracks.

import { AUDIO_FORMATS, BITRATES, SAMPLE_RATES } from './constants';

export interface MusicParams {
  lyrics: string;
  sample_rate: number;
  bitrate: number;
  format: 'mp3' | 'pcm' | 'wav' | 'flac';
}

export const MUSIC_DEFAULTS: MusicParams = {
  // Pre-fill with the [Instrumental] marker so music-2.0 accepts the request
  // out of the box. The user can replace this with real lyrics or section
  // markers ([Verse] / [Chorus] / etc.) — anything non-empty works.
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
    <>
      <div className="field">
        <label>Lyrics <span className="muted" style={{ textTransform: 'none' }}>· required by music-2.0</span></label>
        <textarea
          value={value.lyrics}
          onChange={(e) => set({ lyrics: e.target.value })}
          placeholder="[Verse]&#10;月光洒在旧屋檐&#10;..."
          rows={6}
        />
        <div className="hint">
          music-2.0 必须填 lyrics；纯器乐用 <code>[Instrumental]</code> 占位。可用
          <code>[Verse]</code> / <code>[Chorus]</code> 等段落标记。
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
