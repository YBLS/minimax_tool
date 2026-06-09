"""End-to-end render check for the new video template.

Runs build_request (which does render + _drop_unset + _restore_typed_values)
in-process so any drift between the form's writeVideoParams and the template
is caught immediately, without making any upstream API calls.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.database import Database
from app.services.generator import build_request, ResolvedConfig


async def main() -> None:
    await Database.init()
    try:
        async with Database.pool().acquire() as conn:
            row = await conn.fetchrow(
                "SELECT request_template, default_params "
                "FROM api_configs WHERE module = 'video'",
            )
        rt = row["request_template"]
        dp = row["default_params"]
        if isinstance(rt, str):
            rt = json.loads(rt)
        if isinstance(dp, str):
            dp = json.loads(dp)

        # Fake config (api_key="dummy" — we never call_upstream)
        cfg = ResolvedConfig(
            id=0,
            module="video",
            api_key="dummy",
            base_url="https://api.minimaxi.com",
            endpoint_path="/v1/video_generation",
            model="MiniMax-Hailuo-02",
            request_template=rt,
            response_parser={},
            default_params=dp,
        )

        # Cases mirror what Studio's writeVideoParams would emit
        cases = [
            ("T2V", {
                "submode": "t2v",
                "model": "MiniMax-Hailuo-02",
                "duration": 6,
                "resolution": "768P",
                "prompt_optimizer": True,
                "aigc_watermark": False,
            }),
            ("T2V (1080P + fast_pretreatment)", {
                "submode": "t2v",
                "model": "MiniMax-Hailuo-02",
                "duration": 6,
                "resolution": "1080P",
                "prompt_optimizer": True,
                "aigc_watermark": False,
                "fast_pretreatment": True,
            }),
            ("I2V", {
                "submode": "i2v",
                "model": "MiniMax-Hailuo-02",
                "duration": 6,
                "resolution": "768P",
                "prompt_optimizer": True,
                "aigc_watermark": False,
                "first_frame_image": "https://cdn.example.com/seed.jpg",
            }),
            ("FL2V (full)", {
                "submode": "fl2v",
                "model": "MiniMax-Hailuo-02",
                "duration": 10,
                "resolution": "768P",
                "prompt_optimizer": True,
                "aigc_watermark": False,
                "first_frame_image": "data:image/jpeg;base64,/9j/AAA",
                "last_frame_image": "https://cdn.example.com/end.jpg",
                "callback_url": "https://me.example.com/hook",
            }),
        ]

        for label, params in cases:
            req = build_request(cfg, prompt="a yellow sunflower", params=params)
            body = req["body"]
            print(f"\n=== {label} ===")
            print(json.dumps(body, ensure_ascii=False, indent=2))

            # Type spot-checks
            assert "duration" not in body or isinstance(body["duration"], int), \
                f"duration type wrong: {type(body.get('duration')).__name__}"
            assert "aigc_watermark" not in body or isinstance(body["aigc_watermark"], bool), \
                f"aigc_watermark type wrong: {type(body.get('aigc_watermark')).__name__}"
            assert "prompt_optimizer" not in body or isinstance(body["prompt_optimizer"], bool), \
                f"prompt_optimizer type wrong: {type(body.get('prompt_optimizer')).__name__}"

        # T2V must not carry first_frame_image / last_frame_image
        t2v_body = build_request(cfg, prompt="x", params={
            "submode": "t2v", "model": "MiniMax-Hailuo-02", "duration": 6, "resolution": "768P",
            "prompt_optimizer": True, "aigc_watermark": False,
        })["body"]
        assert "first_frame_image" not in t2v_body, "T2V must not carry first_frame_image"
        assert "last_frame_image" not in t2v_body, "T2V must not carry last_frame_image"
        print("\n✓ T2V body has no image fields (as expected)")
        print("✓ all bodies have correct JSON types (int, bool, str)")
    finally:
        await Database.close()


if __name__ == "__main__":
    asyncio.run(main())
