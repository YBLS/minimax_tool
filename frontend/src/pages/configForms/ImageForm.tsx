// Image generation params — POST /v1/image_generation
// Spec fields: aspect_ratio, n, response_format, prompt_optimizer, aigc_watermark, seed
// https://platform.minimaxi.com/document/ImageGeneration

import { Checkbox, Form, Input, InputNumber, Segmented, Select, Space, Typography } from 'antd';
import { ASPECT_RATIOS, ASPECT_RATIO_SIZES, RESPONSE_FORMATS_IMAGE } from './constants';

export interface ImageParams {
  aspect_ratio: string;
  n: number;
  response_format: 'url' | 'base64';
  prompt_optimizer: boolean;
  aigc_watermark: boolean;
  seed: number | '';
}

export const IMAGE_DEFAULTS: ImageParams = {
  aspect_ratio: '1:1',
  n: 1,
  response_format: 'url',
  prompt_optimizer: false,
  aigc_watermark: false,
  seed: '',
};

export function readImageParams(d: Record<string, any> = {}): ImageParams {
  return {
    aspect_ratio: d.aspect_ratio ?? IMAGE_DEFAULTS.aspect_ratio,
    n: typeof d.n === 'number' ? d.n : (d.n ? Number(d.n) : IMAGE_DEFAULTS.n),
    response_format: d.response_format ?? IMAGE_DEFAULTS.response_format,
    prompt_optimizer: d.prompt_optimizer === true || d.prompt_optimizer === 'true',
    aigc_watermark: d.aigc_watermark === true || d.aigc_watermark === 'true',
    seed: d.seed === '' || d.seed == null ? '' : Number(d.seed),
  };
}

export function writeImageParams(p: ImageParams): Record<string, any> {
  return {
    aspect_ratio: p.aspect_ratio,
    n: p.n,
    response_format: p.response_format,
    prompt_optimizer: p.prompt_optimizer,
    aigc_watermark: p.aigc_watermark,
    ...(p.seed !== '' && p.seed != null ? { seed: p.seed } : {}),
  };
}

interface Props {
  value: ImageParams;
  onChange: (next: ImageParams) => void;
}

export function ImageParamsForm({ value, onChange }: Props) {
  const set = (patch: Partial<ImageParams>) => onChange({ ...value, ...patch });

  return (
    <Space direction="vertical" size={12} style={{ width: '100%' }}>
      <Form.Item label="Aspect ratio">
        <Segmented
          value={value.aspect_ratio}
          onChange={(v) => set({ aspect_ratio: v as string })}
          options={ASPECT_RATIOS.map((ar) => ({
            value: ar,
            label: (
              <div style={{ textAlign: 'center', lineHeight: 1.1 }}>
                <div style={{ fontWeight: 600 }}>{ar}</div>
                <div style={{ fontSize: 10, opacity: 0.7 }}>{ASPECT_RATIO_SIZES[ar]}</div>
              </div>
            ),
          }))}
          block
        />
      </Form.Item>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <Form.Item label="Count (n) · 1–9">
          <InputNumber
            min={1}
            max={9}
            value={value.n}
            onChange={(n) => set({ n: Math.max(1, Math.min(9, Number(n) || 1)) })}
            style={{ width: '100%' }}
          />
        </Form.Item>
        <Form.Item label="Response format">
          <Select
            value={value.response_format}
            onChange={(v) => set({ response_format: v as 'url' | 'base64' })}
            options={RESPONSE_FORMATS_IMAGE.map((f) => ({ value: f, label: f }))}
            style={{ width: '100%' }}
          />
          <div className="field-hint">url 有效期 ~24h；base64 会直接落盘</div>
        </Form.Item>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <Form.Item>
          <Checkbox
            checked={value.prompt_optimizer}
            onChange={(e) => set({ prompt_optimizer: e.target.checked })}
          >
            Optimize prompt
          </Checkbox>
          <div className="field-hint">Auto-rewrite via MiniMax prompt optimizer</div>
        </Form.Item>
        <Form.Item>
          <Checkbox
            checked={value.aigc_watermark}
            onChange={(e) => set({ aigc_watermark: e.target.checked })}
          >
            AIGC watermark
          </Checkbox>
        </Form.Item>
      </div>

      <Form.Item
        label={
          <Space>
            Seed
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              · optional, leave empty for random
            </Typography.Text>
          </Space>
        }
      >
        <Input
          type="number"
          placeholder="(random)"
          value={value.seed}
          onChange={(e) => {
            const v = e.target.value;
            set({ seed: v === '' ? '' : Number(v) });
          }}
        />
        <div className="field-hint">Same seed + same params → similar image, for reproducibility</div>
      </Form.Item>
    </Space>
  );
}
