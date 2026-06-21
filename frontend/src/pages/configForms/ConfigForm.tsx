// Slim Common+Advanced config form. Module-specific per-call params live in Studio.

import { useEffect, useState } from 'react';
import { Button, Form, Input, Space, Typography } from 'antd';
import { ReloadOutlined } from '@ant-design/icons';
import { CommonFields } from './CommonFields';
import { buildRequestTemplate, defaultResponseParser } from './templateBuilders';
import type { ModuleName } from '@/types';

export interface FormConfig {
  id: number;
  module: ModuleName;
  display_name: string;
  key_provider_id: number | null;
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
  // Only set when the user actually touched the provider select; lets us
  // distinguish "leave it alone" from "explicitly unbind".
  key_provider_id?: number | null;
  base_url: string;
  endpoint_path: string;
  model: string;
  enabled: boolean;
  request_template: any;
  response_parser: any;
  default_params?: Record<string, any>;
}

export interface ConfigFormProps {
  config: FormConfig;
  onChange: (next: FormSubmit) => void;
}

export function ConfigForm({ config, onChange }: ConfigFormProps) {
  const [displayName, setDisplayName] = useState(config.display_name);
  const [keyProviderId, setKeyProviderId] = useState<number | null>(config.key_provider_id);
  const [keyProviderDirty, setKeyProviderDirty] = useState(false);
  const [baseUrl, setBaseUrl] = useState(config.base_url);
  const [endpointPath, setEndpointPath] = useState(config.endpoint_path);
  const [model, setModel] = useState(config.model);
  const [enabled, setEnabled] = useState(config.enabled);

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

    const submit: FormSubmit = {
      display_name: displayName,
      base_url: baseUrl,
      endpoint_path: endpointPath,
      model,
      enabled,
      request_template,
      response_parser,
    };
    if (keyProviderDirty) {
      submit.key_provider_id = keyProviderId;
    }
    onChange(submit);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [displayName, keyProviderId, keyProviderDirty, baseUrl, endpointPath, model, enabled, templateText, parserText, templateDirty, parserDirty]);

  const onCommonChange = (patch: any) => {
    if ('display_name' in patch) setDisplayName(patch.display_name);
    if ('key_provider_id'      in patch) {
      setKeyProviderId(patch.key_provider_id);
      setKeyProviderDirty(true);
    }
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
    <Form layout="vertical">
      <Typography.Text
        type="secondary"
        style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: 1, display: 'block', margin: '0 0 8px' }}
      >
        Common
      </Typography.Text>
      <CommonFields
        module={config.module}
        displayName={displayName}
        keyProviderId={keyProviderId}
        keyProviderDirty={keyProviderDirty}
        baseUrl={baseUrl}
        endpointPath={endpointPath}
        model={model}
        enabled={enabled}
        hasApiKey={config.has_api_key}
        onChange={onCommonChange}
      />

      <div className="field-hint" style={{ marginTop: 8, marginBottom: 4, fontSize: 12 }}>
        Per-call parameters (aspect ratio, voice, lyrics, etc.) are configured at the
        generation time in <b>Studio</b> — they don't live here. This config still has a{' '}
        <code>default_params</code> block that Studio pre-fills from.
      </div>

      <div style={{ marginTop: 12 }}>
        <Button
          type="link"
          style={{ padding: 0, height: 'auto' }}
          onClick={() => setShowAdvanced(!showAdvanced)}
        >
          {showAdvanced ? '▾' : '▸'} Advanced · request template & response parser
        </Button>
        {showAdvanced && (
          <div style={{ marginTop: 8 }}>
            <Typography.Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 8 }}>
              模板会根据该模块的 <code>default_params</code> 自动生成（可在 Studio 临时覆盖）。
              改这里 = 切换到手动模式。点 <b>Reset to auto</b> 回到自动模式。
            </Typography.Text>

            <Form.Item
              label={
                <Space style={{ width: '100%' }}>
                  <span>Request template (JSON)</span>
                  <Button
                    type="link"
                    size="small"
                    icon={<ReloadOutlined />}
                    onClick={resetTemplate}
                    disabled={!templateDirty}
                    style={{ marginLeft: 'auto', padding: 0 }}
                  >
                    Reset to auto
                  </Button>
                </Space>
              }
            >
              <Input.TextArea
                value={templateText}
                onChange={(e) => { setTemplateText(e.target.value); setTemplateDirty(true); }}
                spellCheck={false}
                className="json-editor"
              />
            </Form.Item>

            <Form.Item
              label={
                <Space style={{ width: '100%' }}>
                  <span>Response parser (JSON)</span>
                  <Button
                    type="link"
                    size="small"
                    icon={<ReloadOutlined />}
                    onClick={resetParser}
                    disabled={!parserDirty}
                    style={{ marginLeft: 'auto', padding: 0 }}
                  >
                    Reset to default
                  </Button>
                </Space>
              }
            >
              <Input.TextArea
                value={parserText}
                onChange={(e) => { setParserText(e.target.value); setParserDirty(true); }}
                spellCheck={false}
                className="json-editor json-editor-short"
              />
            </Form.Item>
          </div>
        )}
      </div>
    </Form>
  );
}
