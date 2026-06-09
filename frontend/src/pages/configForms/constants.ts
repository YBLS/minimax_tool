// Module-specific constants and presets curated from the MiniMax public API docs.
// https://platform.minimaxi.com/document/  (image_generation / T2A V2 / MusicGeneration / VideoGeneration)

import type { ModuleName } from '@/types';

export const MODEL_PRESETS: Record<ModuleName, string[]> = {
  image: ['image-01', 'image-01-live'],
  // Verified against platform.minimaxi.com docs (2025-12). speech-01 was an
  // older model name; current flagships are speech-2.5-hd-preview / speech-2.6.
  voice: ['speech-2.5-hd-preview', 'speech-2.6-turbo', 'speech-02-hd', 'speech-01-turbo'],
  // music-01 was the seed-era model; current flaghip is music-1.5 / music-2.0.
  music: ['music-1.5', 'music-2.0', 'music-01'],
  // video-01 has been retired; MiniMax-Hailuo-02 is the current model.
  video: ['MiniMax-Hailuo-02', 'video-01'],
};

export const ASPECT_RATIOS = ['1:1', '16:9', '4:3', '3:2', '2:3', '3:4', '9:16', '21:9'] as const;
export const ASPECT_RATIO_SIZES: Record<string, string> = {
  '1:1': '1024×1024', '16:9': '1280×720', '4:3': '1152×864', '3:2': '1248×832',
  '2:3': '832×1248', '3:4': '864×1152', '9:16': '720×1280', '21:9': '1344×576',
};
export const RESPONSE_FORMATS_IMAGE = ['url', 'base64'] as const;

// Curated common voice_ids. The full list is available via
// POST /v1/audio/minimax/voices/list with your API key.
export const VOICE_PRESETS: { id: string; label: string; lang: string }[] = [
  { id: 'female-shaonv',          label: '少女音 (中文女声)',         lang: '中文' },
  { id: 'male-qn-qingse',         label: '青年男声 · 清色',           lang: '中文' },
  { id: 'female-yujie',           label: '御姐音',                     lang: '中文' },
  { id: 'male-qn-jingying',       label: '精英男声',                   lang: '中文' },
  { id: 'Chinese (Mandarin)_News_Anchor',     label: '新闻女声 (官方)', lang: '中文' },
  { id: 'Chinese (Mandarin)_Reliable_Executive', label: '沉稳高管 (官方)', lang: '中文' },
  { id: 'English_Graceful_Woman', label: 'English · Graceful Woman',  lang: '英文' },
  { id: 'English_Trustworth_Man', label: 'English · Trustworth Man',  lang: '英文' },
];

export const SAMPLE_RATES = [8000, 16000, 22050, 24000, 32000, 44100] as const;
export const BITRATES     = [32000, 64000, 128000, 256000] as const;
export const AUDIO_FORMATS = ['mp3', 'pcm', 'wav', 'flac'] as const;
export const CHANNELS     = [1, 2] as const;

export const VOICE_ID_DEFAULT = 'female-shaonv';
