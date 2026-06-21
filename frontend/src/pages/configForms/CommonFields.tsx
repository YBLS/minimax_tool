import { useEffect, useState } from 'react';
import {
  Alert,
  Checkbox,
  Form,
  Input,
  Select,
  Space,
  Tag,
  Typography,
} from 'antd';
import { MODEL_PRESETS } from './constants';
import { api } from '@/api/client';
import type { KeyProvider, ModuleName } from '@/types';

export interface CommonFieldsPatch {
  display_name?: string;
  // null  = "no specific provider, use auto-bind"
  // number= a specific provider id
  key_provider_id?: number | null;
  key_provider_dirty?: boolean;
  base_url?: string;
  endpoint_path?: string;
  model?: string;
  enabled?: boolean;
}

export interface CommonFieldsProps {
  module: ModuleName;
  displayName: string;
  keyProviderId: number | null;
  keyProviderDirty: boolean;
  baseUrl: string;
  endpointPath: string;
  model: string;
  enabled: boolean;
  // True when the bound provider (or the auto-bound one) actually has a key
  // saved on it. Used for the status hint.
  hasApiKey: boolean;
  onChange: (patch: CommonFieldsPatch) => void;
}

export function CommonFields(props: CommonFieldsProps) {
  const {
    module, displayName, keyProviderId, keyProviderDirty,
    baseUrl, endpointPath, model, enabled, hasApiKey, onChange,
  } = props;
  const presets = MODEL_PRESETS[module] ?? [];
  const modelIsPreset = presets.includes(model);

  const [providers, setProviders] = useState<KeyProvider[]>([]);
  const [providersError, setProvidersError] = useState<string | null>(null);
  useEffect(() => {
    api.listKeyProviders()
      .then(setProviders)
      .catch((e) => setProvidersError(String(e?.message ?? e)));
  }, []);

  const enabledProviders = providers.filter((p) => p.enabled);
  const onlyOne = enabledProviders.length === 1;

  // "Auto-bind" is the recommended state: when the user hasn't picked a
  // specific provider AND there's only one enabled one, the value stays
  // null and the backend will resolve it. Show a gentle hint when this is
  // the case so the user knows what's happening.
  const showAutoHint = !keyProviderDirty && keyProviderId == null && onlyOne;
  const showMultiHint = !keyProviderDirty && keyProviderId == null && enabledProviders.length > 1;

  return (
    <>
      <Form.Item label="Display name">
        <Input
          value={displayName}
          onChange={(e) => onChange({ display_name: e.target.value })}
        />
      </Form.Item>

      <Form.Item
        label={
          <Space>
            API Key provider
            {hasApiKey
              ? <Tag color="success" style={{ marginLeft: 4 }}>✓ key set</Tag>
              : <Tag style={{ marginLeft: 4 }}>no key</Tag>}
          </Space>
        }
      >
        <Select
          style={{ width: '100%' }}
          value={keyProviderId ?? '__auto__'}
          onChange={(v) => {
            if (v === '__auto__') {
              onChange({ key_provider_id: null, key_provider_dirty: true });
            } else {
              onChange({ key_provider_id: v as number, key_provider_dirty: true });
            }
          }}
          options={[
            {
              value: '__auto__',
              label: onlyOne
                ? `Auto-bind (only enabled: ${enabledProviders[0].name})`
                : enabledProviders.length === 0
                  ? 'Auto-bind (no enabled providers — will fail)'
                  : `Auto-bind (ambiguous: ${enabledProviders.length} providers)`,
            },
            ...providers.map((p) => ({
              value: p.id,
              label: `${p.name}${!p.enabled ? '  · disabled' : ''}${p.has_api_key ? '  · 🔑' : '  · no key'}`,
            })),
          ]}
          placeholder="Loading providers…"
        />
        {providersError && (
          <Alert type="error" showIcon message={providersError} style={{ marginTop: 8 }} />
        )}
        <div className="field-hint" style={{ marginTop: 4 }}>
          {showAutoHint && (
            <span>
              With one enabled provider, leaving this on <b>Auto-bind</b> lets the runtime
              pick it up automatically. No value is persisted on the config row.
            </span>
          )}
          {showMultiHint && (
            <span>
              {enabledProviders.length} providers are enabled — auto-bind is ambiguous, pick one explicitly.
            </span>
          )}
          {!showAutoHint && !showMultiHint && keyProviderId == null && (
            <span>
              No key provider is currently configured. Create one in the <b>API Keys</b> tab first.
            </span>
          )}
          {keyProviderId != null && (
            <span>
              Saved binding: provider <b>#{keyProviderId}</b>. Clear the selection (switch back to Auto-bind) and Save to unlink.
            </span>
          )}
        </div>
      </Form.Item>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <Form.Item label="Base URL">
          <Input
            value={baseUrl}
            onChange={(e) => onChange({ base_url: e.target.value })}
          />
        </Form.Item>
        <Form.Item label="Endpoint path">
          <Input
            value={endpointPath}
            onChange={(e) => onChange({ endpoint_path: e.target.value })}
          />
        </Form.Item>
      </div>

      <Form.Item label="Model">
        <Input
          list={`${module}-models`}
          value={model}
          onChange={(e) => onChange({ model: e.target.value })}
        />
        <datalist id={`${module}-models`}>
          {presets.map((m) => <option key={m} value={m} />)}
        </datalist>
        <div className="field-hint">
          {modelIsPreset
            ? `Preset · ${presets.length} known models`
            : 'Custom · not in the preset list (you can still type any value)'}
        </div>
      </Form.Item>

      <Form.Item>
        <Checkbox
          checked={enabled}
          onChange={(e) => onChange({ enabled: e.target.checked })}
        >
          Enabled — use this config for the module
        </Checkbox>
      </Form.Item>
    </>
  );
}
