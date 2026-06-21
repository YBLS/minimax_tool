// Tiny fetch wrapper. All endpoints are mounted at /api.

import type {
  ApiConfig,
  ConfigCreate,
  ConfigTestResult,
  ConfigUpdate,
  GenerateRequest,
  GenerateResult,
  HealthInfo,
  HistoryDetail,
  HistoryItem,
  KeyProvider,
  KeyProviderCreate,
  KeyProviderTestResult,
  KeyProviderUpdate,
  ModuleName,
  SecretMeta,
  TranslateRequest,
  TranslateResult,
} from '@/types';

const BASE = '';  // same origin

class ApiError extends Error {
  status: number;
  body: any;
  constructor(status: number, body: any, message: string) {
    super(message);
    this.status = status;
    this.body = body;
  }
}

async function http<T>(method: string, path: string, body?: any): Promise<T> {
  const init: RequestInit = {
    method,
    headers: { 'Content-Type': 'application/json' },
  };
  if (body !== undefined) init.body = JSON.stringify(body);
  const resp = await fetch(BASE + path, init);
  const text = await resp.text();
  let parsed: any = text;
  try { parsed = text ? JSON.parse(text) : null; } catch {}
  if (!resp.ok) {
    const detail = parsed?.detail ?? parsed?.message ?? text;
    throw new ApiError(resp.status, parsed, typeof detail === 'string' ? detail : `HTTP ${resp.status}`);
  }
  return parsed as T;
}

export const api = {
  // health
  health: () => http<HealthInfo>('GET', '/api/health'),

  // configs
  listConfigs: () => http<ApiConfig[]>('GET', '/api/configs'),
  getConfig: (module: ModuleName) => http<ApiConfig>('GET', `/api/configs/${module}`),
  createConfig: (body: ConfigCreate) => http<ApiConfig>('POST', '/api/configs', body),
  updateConfig: (id: number, body: ConfigUpdate) => http<ApiConfig>('PUT', `/api/configs/${id}`, body),
  deleteConfig: (id: number) => http<{ ok: boolean }>('DELETE', `/api/configs/${id}`),
  testConfig: (id: number) => http<ConfigTestResult>('POST', `/api/configs/${id}/test`),

  // key providers (decoupled API key storage)
  listKeyProviders: () => http<KeyProvider[]>('GET', '/api/key-providers'),
  getKeyProvider: (id: number) => http<KeyProvider>('GET', `/api/key-providers/${id}`),
  createKeyProvider: (body: KeyProviderCreate) => http<KeyProvider>('POST', '/api/key-providers', body),
  updateKeyProvider: (id: number, body: KeyProviderUpdate) => http<KeyProvider>('PUT', `/api/key-providers/${id}`, body),
  deleteKeyProvider: (id: number) => http<{ ok: boolean }>('DELETE', `/api/key-providers/${id}`),
  testKeyProvider: (id: number) => http<KeyProviderTestResult>('POST', `/api/key-providers/${id}/test`),

  // generate
  generate: (module: ModuleName, body: GenerateRequest) =>
    http<GenerateResult>('POST', `/api/generate/${module}`, body),

  // history
  // `module` is free-form: matches the DB column (VARCHAR(50)) and the
  // ConfigCreate.module shape. ModuleName alone would reject 'translate',
  // which the History page uses as a filter chip.
  listHistory: (params: { module?: ModuleName | (string & {}); limit?: number; offset?: number } = {}) => {
    const q = new URLSearchParams();
    if (params.module) q.set('module', params.module);
    if (params.limit) q.set('limit', String(params.limit));
    if (params.offset) q.set('offset', String(params.offset));
    const qs = q.toString();
    return http<HistoryItem[]>('GET', `/api/history${qs ? `?${qs}` : ''}`);
  },
  getHistory: (id: number) => http<HistoryDetail>('GET', `/api/history/${id}`),
  deleteHistory: (id: number) => http<{ ok: boolean }>('DELETE', `/api/history/${id}`),

  // secrets
  listSecrets: () => http<SecretMeta[]>('GET', '/api/secrets'),
  upsertSecret: (name: string, value: string, description: string = '') =>
    http<{ ok: boolean }>('PUT', `/api/secrets/${name}`, { value, description }),
  deleteSecret: (name: string) => http<{ ok: boolean }>('DELETE', `/api/secrets/${name}`),

  // translate
  translate: (body: TranslateRequest) => http<TranslateResult>('POST', '/api/translate', body),
};

export { ApiError };
