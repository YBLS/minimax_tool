// Type definitions mirroring the backend Pydantic models.

export type ModuleName = 'image' | 'voice' | 'music' | 'video' | 'translate';
export type StatusName = 'pending' | 'running' | 'success' | 'failed';

// --- Translate --------------------------------------------------------------

export interface TranslateRequest {
  text: string;
  source: string;     // 'auto' | 'zh' | 'en' | ...
  target: string;     // 'zh' | 'en' | ...
  config_id?: number;
  // Per-call model override. Omit to use the config row's `model`.
  model?: string;
}

export interface TranslateResult {
  translated_text: string;
  source: string;
  target: string;
  model: string;
  duration_ms: number;
  // Echoed back so the UI can show "auto-detected: ..." without re-asking
  detected_source?: string;
}

// --- Key Providers ----------------------------------------------------------
//
// API keys live in their own table. A config references one provider via
// `key_provider_id`; if it leaves that null, the backend auto-binds to the
// single enabled provider (the common single-key case).

export interface KeyProvider {
  id: number;
  name: string;
  description: string;
  has_api_key: boolean;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface KeyProviderCreate {
  name: string;
  description?: string;
  api_key?: string;
  enabled?: boolean;
}

export interface KeyProviderUpdate {
  name?: string;
  description?: string;
  api_key?: string;
  enabled?: boolean;
}

export interface KeyProviderTestResult {
  ok: boolean;
  message: string;
  latency_ms: number;
  http_status?: number;
  sample_response?: any;
}

// --- Configs ----------------------------------------------------------------

export interface ApiConfig {
  id: number;
  module: ModuleName;
  display_name: string;
  // The link to a key provider. Null means "auto-bind" (the backend will
  // pick the only enabled provider, or error if there are several).
  key_provider_id: number | null;
  key_provider_name: string | null;
  // Resolved from the linked provider — never reflects the (legacy) key
  // embedded on the config row.
  has_api_key: boolean;
  base_url: string;
  endpoint_path: string;
  model: string;
  request_template: Record<string, any>;
  response_parser: Record<string, any>;
  default_params: Record<string, any>;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface ConfigCreate {
  module: ModuleName;
  display_name: string;
  // Optional. Omit (or pass null) to let the backend auto-bind to the only
  // enabled key provider, or to fail loudly if there are several.
  key_provider_id?: number | null;
  base_url: string;
  endpoint_path: string;
  model: string;
  request_template: Record<string, any>;
  response_parser: Record<string, any>;
  default_params?: Record<string, any>;
  enabled?: boolean;
}

export interface ConfigUpdate {
  display_name?: string;
  // `key_provider_id` is sent only when the user explicitly picks a
  // provider in the form. Use `null` to clear the binding.
  key_provider_id?: number | null;
  base_url?: string;
  endpoint_path?: string;
  model?: string;
  request_template?: Record<string, any>;
  response_parser?: Record<string, any>;
  default_params?: Record<string, any>;
  enabled?: boolean;
}

export interface ConfigTestResult {
  ok: boolean;
  message: string;
  latency_ms: number;
  http_status?: number;
  sample_response?: any;
}

export interface OutputFile {
  type: string;
  url: string;
  size: number;
  mime_type: string;
  path: string;
  source_url?: string;
}

export interface GenerateRequest {
  prompt: string;
  params?: Record<string, any>;
  config_id?: number;
}

export interface GenerateResult {
  id: number;
  module: ModuleName;
  status: StatusName;
  prompt: string;
  params: Record<string, any>;
  output_files: OutputFile[];
  error_message: string;
  duration_ms: number;
  created_at: string;
}

export interface HistoryItem {
  id: number;
  module: ModuleName;
  config_id: number | null;
  prompt: string;
  status: StatusName;
  output_files: OutputFile[];
  error_message: string;
  duration_ms: number;
  created_at: string;
}

export interface HistoryDetail extends HistoryItem {
  params: Record<string, any>;
  request_payload: Record<string, any>;
  response_payload: Record<string, any>;
}

export interface SecretMeta {
  name: string;
  description: string;
  has_value: boolean;
  created_at: string;
  updated_at: string;
}

export interface HealthInfo {
  status: 'ok' | 'degraded';
  db: boolean;
  version?: string;
  error?: string;
}
