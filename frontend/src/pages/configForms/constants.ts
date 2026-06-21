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
  // Chat models exposed by MiniMax for general text tasks (translation,
  // summarisation, etc.). Newer flagships first; abab6.5* kept for legacy
  // accounts that still have access.
  //   MiniMax-M3          — 2026-06, 1M context, MSA architecture, multimodal
  //   MiniMax-M2.7-highspeed — M2.7 with higher TPS, same quality
  //   MiniMax-M2.7        — 2026-04, current open-source flagship
  //   MiniMax-M2          — 2025-10, prior flagship (still default seed)
  //   MiniMax-Text-01     — 2025-01, 4M context, MoE
  //   abab6.5s-chat       — 2024-04, 200k context, legacy
  //   abab6.5-chat        — 2024-04, 200k context, legacy
  translate: [
    'MiniMax-M3',
    'MiniMax-M2.7-highspeed',
    'MiniMax-M2.7',
    'MiniMax-M2',
    'MiniMax-Text-01',
    'abab6.5s-chat',
    'abab6.5-chat',
  ],
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

// Language catalogue for the Translate page. `code` is what gets shipped to
// the backend; `name` is the human-readable name we render in the prompt.
export interface LanguageDef {
  code: string;       // 'zh' / 'en' / ...
  name: string;       // '中文' / 'English' / ...
  short: string;      // '中' / 'EN' / ...  for the chip-style selectors
}

export const TRANSLATE_LANGUAGES: LanguageDef[] = [
  { code: 'zh', name: '中文 (简体)',         short: '中' },
  { code: 'zh-TW', name: '中文 (繁体)',      short: '繁' },
  { code: 'en', name: 'English',             short: 'EN' },
  { code: 'ja', name: '日本語',              short: 'JA' },
  { code: 'ko', name: '한국어',              short: 'KO' },
  { code: 'fr', name: 'Français',            short: 'FR' },
  { code: 'de', name: 'Deutsch',             short: 'DE' },
  { code: 'es', name: 'Español',             short: 'ES' },
  { code: 'ru', name: 'Русский',             short: 'RU' },
  { code: 'pt', name: 'Português',           short: 'PT' },
  { code: 'it', name: 'Italiano',            short: 'IT' },
  { code: 'ar', name: 'العربية',             short: 'AR' },
];

export const TRANSLATE_SOURCE_AUTO: LanguageDef = { code: 'auto', name: 'Auto-detect', short: 'AUTO' };

export function languageName(code: string): string {
  if (code === 'auto') return TRANSLATE_SOURCE_AUTO.name;
  return TRANSLATE_LANGUAGES.find((l) => l.code === code)?.name ?? code;
}
