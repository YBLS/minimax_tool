import { useState } from 'react';
import { MODEL_PRESETS } from './constants';
import type { ModuleName } from '@/types';

export interface CommonFieldsProps {
  module: ModuleName;
  displayName: string;
  apiKey: string;
  baseUrl: string;
  endpointPath: string;
  model: string;
  enabled: boolean;
  hasApiKey: boolean;
  onChange: (patch: Partial<{
    display_name: string;
    api_key: string;
    base_url: string;
    endpoint_path: string;
    model: string;
    enabled: boolean;
  }>) => void;
}

export function CommonFields(props: CommonFieldsProps) {
  const { module, displayName, apiKey, baseUrl, endpointPath, model, enabled, hasApiKey, onChange } = props;
  const [showKey, setShowKey] = useState(false);
  const presets = MODEL_PRESETS[module];
  const modelIsPreset = presets.includes(model);

  return (
    <>
      <div className="field">
        <label>Display name</label>
        <input value={displayName} onChange={(e) => onChange({ display_name: e.target.value })} />
      </div>

      <div className="field">
        <label>
          API key{' '}
          {hasApiKey ? (
            <span className="tag success" style={{ marginLeft: 4, textTransform: 'none' }}>✓ saved</span>
          ) : (
            <span className="tag" style={{ marginLeft: 4, textTransform: 'none' }}>not set</span>
          )}
        </label>
        <div className="row" style={{ gap: 6 }}>
          <input
            type={showKey ? 'text' : 'password'}
            placeholder={hasApiKey ? 'leave blank to keep current value' : 'paste key here'}
            value={apiKey}
            onChange={(e) => onChange({ api_key: e.target.value })}
            autoComplete="off"
            spellCheck={false}
          />
          <button type="button" className="ghost" onClick={() => setShowKey(!showKey)}>
            {showKey ? 'Hide' : 'Show'}
          </button>
          {hasApiKey && (
            <button
              type="button"
              className="danger"
              onClick={() => onChange({ api_key: '' })}
              title="Remove the currently saved key"
            >
              Clear
            </button>
          )}
        </div>
        <div className="hint">
          {apiKey.trim()
            ? <span style={{ color: 'var(--warning)' }}>Will replace the current key on Save.</span>
            : hasApiKey
              ? <span>The saved key is <b>encrypted at rest</b> in PostgreSQL (Fernet + your <code>.master_key</code>). Leave this field blank and click Save to keep it.</span>
              : <span>Paste your MiniMax API key here. It will be encrypted before storage.</span>}
        </div>
      </div>

      <div className="grid-2">
        <div className="field">
          <label>Base URL</label>
          <input value={baseUrl} onChange={(e) => onChange({ base_url: e.target.value })} />
        </div>
        <div className="field">
          <label>Endpoint path</label>
          <input value={endpointPath} onChange={(e) => onChange({ endpoint_path: e.target.value })} />
        </div>
      </div>

      <div className="field">
        <label>Model</label>
        <input
          list={`${module}-models`}
          value={model}
          onChange={(e) => onChange({ model: e.target.value })}
        />
        <datalist id={`${module}-models`}>
          {presets.map((m) => <option key={m} value={m} />)}
        </datalist>
        <div className="hint">
          {modelIsPreset
            ? `Preset · ${presets.length} known models`
            : `Custom · not in the preset list (you can still type any value)`}
        </div>
      </div>

      <div className="field checkbox-row">
        <input
          type="checkbox"
          id="enabled"
          checked={enabled}
          onChange={(e) => onChange({ enabled: e.target.checked })}
        />
        <label htmlFor="enabled" style={{ marginBottom: 0, textTransform: 'none' }}>
          Enabled — use this config for the module
        </label>
      </div>
    </>
  );
}
