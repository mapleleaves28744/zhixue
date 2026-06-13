# Zhixue IP Asset Pack

This folder contains the first mascot asset pack for Zhixue Workshop desktop-pet exploration.

## Mascot Family

| Mascot | Role | Visual Keywords |
| --- | --- | --- |
| ZhiZhi | LLM Wiki companion | book hat, teal scholar cape, source nodes, wiki pages |
| LuLu | learning path and task-status companion | compass badge, route cloud ears, map backpack, reminder bell |
| DianDian | practice, diagnosis, and review companion | yellow spark seed, leaf cape, pencil wand, quiz pouch |

## Files

- `proposal/`: full IP proposal boards with main image, three-view, expressions, scenes, actions, poster, and merch concepts.
- `standards/`: single-character standard sheets with palette, ratio, turnaround, accessories, and idle/remind/focus/done frame guidance.
- `stickers/`: transparent PNG expression cutouts.
- `stickers/*-source.png`: original chroma-key expression sheets used for cutting.
- `hyperframes-pet-preview/`: HyperFrames preview project for animated desktop-pet state cycling.

## HyperFrames Preview

Run from `docs/ip-assets/hyperframes-pet-preview`:

```powershell
npm run dev -- --port 3017
```

Open:

```text
http://localhost:3017/#project/hyperframes-pet-preview
```

Rendering MP4 requires FFmpeg:

```powershell
npm run render -- --output renders/zhixue-pet-state-preview.mp4 --quality draft
```

## Current State Names

Each mascot has four desktop-pet preview states under `hyperframes-pet-preview/assets/pets/<mascot>/`:

- `idle.png`
- `remind.png`
- `focus.png`
- `done.png`

Each mascot also has 12 transparent expression PNG files under `stickers/<mascot>/`.
