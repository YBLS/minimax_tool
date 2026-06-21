// Build request_template from form values for each module.
// Placeholder syntax: {{key:typename|default}}
//   typename: s (string, default) | i (int) | n (number) | b (bool) | j (json literal)
// The template engine (backend services/generator.py) coerces values to the
// requested type so the wire payload has correct JSON types (true, not "true").

import type { ModuleName } from '@/types';

const DEFAULT_HEADERS = {
  Authorization: 'Bearer {{api_key}}',
  'Content-Type': 'application/json',
};

// {{key:typename|default}}
function t(key: string, type: 's' | 'i' | 'n' | 'b' | 'j', def: any): string {
  return `{{${key}:${type}|${def}}}`;
}

function defaultsOf(d: Record<string, any>) {
  return {
    aspect_ratio: '1:1', n: 1, response_format: 'url',
    prompt_optimizer: false, aigc_watermark: false, seed: '',
    ...d,
  };
}

export function buildRequestTemplate(module: ModuleName, raw: Record<string, any>): any {
  switch (module) {
    case 'image': {
      const d = defaultsOf(raw);
      return {
        method: 'POST',
        headers: { ...DEFAULT_HEADERS },
        body: {
          model: '{{model}}',
          prompt: '{{prompt}}',
          aspect_ratio: t('aspect_ratio', 's', d.aspect_ratio),
          n: t('n', 'i', d.n),
          response_format: t('response_format', 's', d.response_format),
          prompt_optimizer: t('prompt_optimizer', 'b', d.prompt_optimizer),
          aigc_watermark: t('aigc_watermark', 'b', d.aigc_watermark),
          ...(d.seed !== '' && d.seed != null ? { seed: t('seed', 'i', d.seed) } : {}),
        },
      };
    }
    case 'voice': {
      const d = {
        voice_id: 'female-shaonv', speed: 1.0, vol: 1.0, pitch: 0,
        sample_rate: 32000, bitrate: 128000, format: 'mp3', channel: 1,
        ...raw,
      };
      return {
        method: 'POST',
        headers: { ...DEFAULT_HEADERS },
        body: {
          model: '{{model}}',
          text: '{{prompt}}',
          voice_setting: {
            voice_id: t('voice_id', 's', d.voice_id),
            speed: t('speed', 'n', d.speed),
            vol: t('vol', 'n', d.vol),
            pitch: t('pitch', 'i', d.pitch),
          },
          audio_setting: {
            sample_rate: t('sample_rate', 'i', d.sample_rate),
            bitrate: t('bitrate', 'i', d.bitrate),
            format: t('format', 's', d.format),
            channel: t('channel', 'i', d.channel),
          },
        },
      };
    }
    case 'music': {
      const d = { sample_rate: 32000, bitrate: 128000, format: 'mp3', lyrics: '', ...raw };
      return {
        method: 'POST',
        headers: { ...DEFAULT_HEADERS },
        body: {
          model: '{{model}}',
          prompt: '{{prompt}}',
          lyrics: t('lyrics', 's', d.lyrics || ''),
          audio_setting: {
            sample_rate: t('sample_rate', 'i', d.sample_rate),
            bitrate: t('bitrate', 'i', d.bitrate),
            format: t('format', 's', d.format),
          },
        },
      };
    }
    case 'video': {
      return {
        method: 'POST',
        headers: { ...DEFAULT_HEADERS },
        body: {
          model: '{{model}}',
          prompt: '{{prompt}}',
        },
      };
    }
    case 'translate': {
      // Translate is implemented as a dedicated backend service that talks to
      // /v1/chat/completions. The request_template below is just a placeholder
      // shown in the "Advanced" JSON editor (the translate service does not
      // actually use it); we keep it valid so the form doesn't blow up.
      return {
        method: 'POST',
        headers: { ...DEFAULT_HEADERS },
        body: {
          model: '{{model}}',
          messages: [
            { role: 'system', content: 'You are a translator.' },
            { role: 'user', content: '{{prompt}}' },
          ],
          temperature: 0.3,
        },
      };
    }
  }
}

// Build response_parser from the module's default. Hidden in "Advanced" UI;
// user can override in the JSON textarea.
export function defaultResponseParser(module: ModuleName): any {
  switch (module) {
    case 'image':
      return {
        type: 'jsonpath',
        items_path: '$.data.image_urls',
        default_ext: 'png',
      };
    case 'voice':
      return {
        type: 'binary',
        content_type_header: 'content-type',
        default_ext: 'mp3',
      };
    case 'music':
      return {
        type: 'minimax_music',
        items_path: '$.data',
        default_ext: 'mp3',
      };
    case 'video':
      return {
        type: 'async_task',
        task_id_path: '$.task_id',
        query_method: 'GET',
        query_path: '/v1/query/video_generation',
        query_params: { task_id: '{{task_id}}' },
        terminal_statuses: ['Success', 'Finished', 'success', 'finished'],
        failed_statuses: ['Fail', 'Failed', 'failure'],
        file_id_path: '$.file_id',
        download_method: 'POST',
        download_path: '/v1/files/retrieve',
        download_body: { file_id: '{{file_id}}' },
        download_url_path: '$.file.download_url',
        default_ext: 'mp4',
        poll_interval: 5.0,
        max_wait: 600.0,
      };
    case 'translate':
      // The translate service does not use the parser. Kept here so the form
      // renders a valid JSON blob in the "Advanced" section.
      return {
        type: 'jsonpath',
        items_path: '$.choices[0].message.content',
      };
  }
}
