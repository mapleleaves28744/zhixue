# Zhixue Workshop Changes

This OpenMAIC snapshot is integrated and modified for the Zhixue Workshop
competition project.

## Existing Local Improvements

- Added Xiaomi MiMo V2.5 and Token Plan regional endpoint support.
- Added Xiaomi MiMo TTS provider support using `mimo-v2.5-tts`.
- Added Xiaomi MiMo ASR provider support using `mimo-v2.5-asr`.
- Added server-side provider configuration and related tests.

## Zhixue Integration

- OpenMAIC runs as an independent repository-contained service.
- Classroom generation APIs require an internal service token.
- Classroom playback accepts short-lived signed access from the Zhixue backend.
- A classroom manifest API exposes generated scenes to the authorized Zhixue
  backend for narrated and subtitled MP4 export.
- Zhixue remains the source of truth for users, courses, RAG citations, student
  profiles, media jobs, learning records, and permissions.

See `docs/superpowers/specs/2026-06-13-openmaic-immersive-classroom-video-design.md`
in the parent repository for the integration design.
