// Image generation params — POST /v1/image_generation
// Spec fields: aspect_ratio, n, response_format, prompt_optimizer, aigc_watermark, seed
// https://platform.minimaxi.com/document/ImageGeneration

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
    <>
      <div className="field">
        <label>Aspect ratio</label>
        <div className="row" style={{ flexWrap: 'wrap', gap: 6 }}>
          {ASPECT_RATIOS.map((ar) => (
            <button
              key={ar}
              type="button"
              className={value.aspect_ratio === ar ? 'primary' : ''}
              onClick={() => set({ aspect_ratio: ar })}
              style={{ padding: '6px 10px' }}
              title={ASPECT_RATIO_SIZES[ar]}
            >
              <span style={{ fontWeight: 600 }}>{ar}</span>{' '}
              <span className="muted" style={{ fontSize: 11 }}>{ASPECT_RATIO_SIZES[ar]}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="grid-2">
        <div className="field">
          <label>Count (n) <span className="muted" style={{ textTransform: 'none' }}>· 1–9</span></label>
          <input
            type="number"
            min={1}
            max={9}
            value={value.n}
            onChange={(e) => set({ n: Math.max(1, Math.min(9, Number(e.target.value) || 1)) })}
          />
        </div>
        <div className="field">
          <label>Response format</label>
          <select value={value.response_format} onChange={(e) => set({ response_format: e.target.value as any })}>
            {RESPONSE_FORMATS_IMAGE.map((f) => <option key={f} value={f}>{f}</option>)}
          </select>
          <div className="hint">url 有效期 ~24h；base64 会直接落盘</div>
        </div>
      </div>

      <div className="grid-2">
        <div className="field checkbox-row">
          <input
            type="checkbox"
            id="img-opt"
            checked={value.prompt_optimizer}
            onChange={(e) => set({ prompt_optimizer: e.target.checked })}
          />
          <label htmlFor="img-opt" style={{ marginBottom: 0, textTransform: 'none' }}>
            Optimize prompt (auto-rewrite via MiniMax prompt optimizer)
          </label>
        </div>
        <div className="field checkbox-row">
          <input
            type="checkbox"
            id="img-wm"
            checked={value.aigc_watermark}
            onChange={(e) => set({ aigc_watermark: e.target.checked })}
          />
          <label htmlFor="img-wm" style={{ marginBottom: 0, textTransform: 'none' }}>
            AIGC watermark
          </label>
        </div>
      </div>

      <div className="field">
        <label>Seed <span className="muted" style={{ textTransform: 'none' }}>· optional, leave empty for random</span></label>
        <input
          type="number"
          placeholder="(random)"
          value={value.seed}
          onChange={(e) => {
            const v = e.target.value;
            set({ seed: v === '' ? '' : Number(v) });
          }}
        />
        <div className="hint">Same seed + same params → similar image, for reproducibility</div>
      </div>
    </>
  );
}
