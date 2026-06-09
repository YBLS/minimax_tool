// Slim Common+Advanced config form. Module-specific per-call params live in Studio.
// Keeps default_params as the underlying "defaults" field (still editable via Advanced
// in the JSON request_template), but doesn't surface a giant per-module form here.

import { useEffect, useState } from 'react';
import { CommonFields } from './CommonFields';
import { buildRequestTemplate, defaultResponseParser } from './templateBuilders';
import type { ModuleName } from '@/types';

export interface FormConfig {
  id: number;
  module: ModuleName;
  display_name: string;
  base_url: string;
  endpoint_path: string;
  model: string;
  enabled: boolean;
  has_api_key: boolean;
  default_params: Record<string, any>;
  request_template: any;
  response_parser: any;
}

export interface FormSubmit {
  display_name: string;
  api_key?: string;
  base_url: string;
  endpoint_path: string;
  model: string;
  enabled: boolean;
  request_template: any;
  response_parser: any;
}

export interface ConfigFormProps {
  config: FormConfig;
  onChange: (next: FormSubmit) => void;
}

export function ConfigForm({ config, onChange }: ConfigFormProps) {
  const [displayName, setDisplayName] = useState(config.display_name);
  const [apiKey, setApiKey] = useState('');
  const [apiKeyDirty, setApiKeyDirty] = useState(false);  // user typed OR clicked Clear this session
  const [baseUrl, setBaseUrl] = useState(config.base_url);
  const [endpointPath, setEndpointPath] = useState(config.endpoint_path);
  const [model, setModel] = useState(config.model);
  const [enabled, setEnabled] = useState(config.enabled);

  // Advanced
  const [templateText, setTemplateText] = useState(() => JSON.stringify(config.request_template, null, 2));
  const [parserText, setParserText] = useState(() => JSON.stringify(config.response_parser, null, 2));
  const [templateDirty, setTemplateDirty] = useState(false);
  const [parserDirty, setParserDirty] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);

  useEffect(() => {
    let request_template: any;
    let response_parser: any;

    if (templateDirty) {
      try { request_template = JSON.parse(templateText); } catch { /* invalid JSON, ignored until fixed */ }
    } else {
      request_template = buildRequestTemplate(config.module, config.default_params || {});
    }
    if (parserDirty) {
      try { response_parser = JSON.parse(parserText); } catch { /* invalid JSON, ignored */ }
    } else {
      response_parser = config.response_parser || defaultResponseParser(config.module);
    }

    // Only include api_key in the body if the user actually touched it this
    // session — otherwise the server keeps the current encrypted value. This
    // also lets the Clear button (which sets apiKey='') actually clear by
    // including the field as an empty string in the body.
    const submit: FormSubmit = {
      display_name: displayName,
      base_url: baseUrl,
      endpoint_path: endpointPath,
      model,
      enabled,
      request_template,
      response_parser,
    };
    if (apiKeyDirty) {
      submit.api_key = apiKey;
    }
    onChange(submit);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [displayName, apiKey, apiKeyDirty, baseUrl, endpointPath, model, enabled, templateText, parserText, templateDirty, parserDirty]);

  const onCommonChange = (patch: any) => {
    if ('display_name' in patch) setDisplayName(patch.display_name);
    if ('api_key'      in patch) { setApiKey(patch.api_key); setApiKeyDirty(true); }
    if ('base_url'     in patch) setBaseUrl(patch.base_url);
    if ('endpoint_path' in patch) setEndpointPath(patch.endpoint_path);
    if ('model'        in patch) setModel(patch.model);
    if ('enabled'      in patch) setEnabled(patch.enabled);
  };

  const resetTemplate = () => {
    setTemplateDirty(false);
    setTemplateText(JSON.stringify(buildRequestTemplate(config.module, config.default_params || {}), null, 2));
  };

  const resetParser = () => {
    setParserDirty(false);
    setParserText(JSON.stringify(defaultResponseParser(config.module), null, 2));
  };

  return (
    <>
      <h4 className="muted" style={{ margin: '0 0 8px', textTransform: 'uppercase', fontSize: 11, letterSpacing: 1 }}>Common</h4>
      <CommonFields
        module={config.module}
        displayName={displayName}
        apiKey={apiKey}
        baseUrl={baseUrl}
        endpointPath={endpointPath}
        model={model}
        enabled={enabled}
        hasApiKey={config.has_api_key}
        onChange={onCommonChange}
      />

      <div className="hint" style={{ marginTop: 8, marginBottom: 4, fontSize: 12 }}>
        Per-call parameters (aspect ratio, voice, lyrics, etc.) are configured at the
        generation time in <b>Studio</b> — they don't live here.
        This config still has a <code>default_params</code> block that Studio pre-fills from.
      </div>

      <details style={{ marginTop: 12 }} open={showAdvanced} onToggle={(e) => setShowAdvanced((e.target as HTMLDetailsElement).open)}>
        <summary style={{ cursor: 'pointer', color: 'var(--text-dim)', fontSize: 12, textTransform: 'uppercase', letterSpacing: 1 }}>
          Advanced · request template & response parser
        </summary>
        <div className="hint" style={{ marginTop: 8, marginBottom: 12 }}>
          模板会根据该模块的 <code>default_params</code> 自动生成（可在 Studio 临时覆盖）。
          改这里 = 切换到手动模式。点 <b>Reset to auto</b> 回到自动模式。
        </div>

        <div className="field">
          <div className="row">
            <label style={{ marginBottom: 0 }}>Request template (JSON)</label>
            <div className="spacer" />
            <button type="button" className="ghost" onClick={resetTemplate} disabled={!templateDirty}>Reset to auto</button>
          </div>
          <textarea
            value={templateText}
            onChange={(e) => { setTemplateText(e.target.value); setTemplateDirty(true); }}
            spellCheck={false}
            style={{ minHeight: 200, fontFamily: 'ui-monospace, SFMono-Regular, monospace' }}
          />
        </div>

        <div className="field">
          <div className="row">
            <label style={{ marginBottom: 0 }}>Response parser (JSON)</label>
            <div className="spacer" />
            <button type="button" className="ghost" onClick={resetParser} disabled={!parserDirty}>Reset to default</button>
          </div>
          <textarea
            value={parserText}
            onChange={(e) => { setParserText(e.target.value); setParserDirty(true); }}
            spellCheck={false}
            style={{ minHeight: 120, fontFamily: 'ui-monospace, SFMono-Regular, monospace' }}
          />
        </div>
      </details>
    </>
  );
}
