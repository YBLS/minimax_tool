// Shared form state shape for all modules.
import type { ModuleName } from '@/types';

export interface CommonFields {
  display_name: string;
  api_key: string;          // user input; empty = keep current
  base_url: string;
  endpoint_path: string;
  model: string;
  enabled: boolean;
}

export type FormState = CommonFields & {
  // Module-specific key/values that go into default_params
  default_params: Record<string, any>;
  // Advanced — raw JSON, optional
  request_template?: any;
  response_parser?: any;
  // Bookkeeping
  templateDirty?: boolean;
  parserDirty?: boolean;
  module: ModuleName;
};
