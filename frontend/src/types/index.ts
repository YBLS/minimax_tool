// Type definitions mirroring the backend Pydantic models.

export type ModuleName = 'image' | 'voice' | 'music' | 'video';
export type StatusName = 'pending' | 'running' | 'success' | 'failed';

export interface ApiConfig {
  id: number;
  module: ModuleName;
  display_name: string;
  base_url: string;
  endpoint_path: string;
  model: string;
  request_template: Record<string, any>;
  response_parser: Record<string, any>;
  default_params: Record<string, any>;
  enabled: boolean;
  has_api_key: boolean;
  created_at: string;
  updated_at: string;
}

export interface ConfigCreate {
  module: ModuleName;
  display_name: string;
  api_key?: string;
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
  api_key?: string;
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
