from __future__ import annotations

import argparse
import asyncio
import json

from app.llm.multimodal_provider import build_multimodal_provider


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", action="store_true")
    parser.add_argument("--video", action="store_true")
    parser.add_argument("--prompt", default="A clean educational illustration of BFS graph traversal")
    args = parser.parse_args()

    provider = build_multimodal_provider()
    print(f"provider={provider.provider_name}")

    if args.image:
        result = await provider.generate_image(prompt=args.prompt, size="1024x768", style="clean educational")
        print(json.dumps({
            "provider": result.provider,
            "model": result.model,
            "mime_type": result.mime_type,
            "bytes": len(result.image_bytes),
            "raw_keys": list(result.raw.keys())[:20],
        }, ensure_ascii=False, indent=2))

    if args.video:
        result = await provider.create_video_job(prompt=args.prompt, duration_seconds=8, size="1280x720")
        print(json.dumps({
            "provider": result.provider,
            "model": result.model,
            "status": result.status,
            "provider_job_id": result.provider_job_id,
            "video_url": result.video_url,
            "raw": result.raw,
        }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
