// Shared form state shape for all modules.
import type { ModuleName } from '@/types';

export interface CommonFields {
  display_name: string;
  // null  = "auto-bind to the only enabled key provider, or fail loudly"
  // number= a specific key_provider row to link to
  key_provider_id: number | null;
  key_provider_dirty: boolean;     // true when the user explicitly picked/changed
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
