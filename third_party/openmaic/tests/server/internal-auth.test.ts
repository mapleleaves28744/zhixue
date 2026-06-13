import { describe, expect, it } from 'vitest';
import {
  buildPlaybackToken,
  isInternalRequest,
  verifyPlaybackToken,
} from '@/lib/server/internal-auth';

describe('OpenMAIC internal auth', () => {
  it('accepts only the configured internal token', () => {
    const valid = new Request('http://localhost/api/generate-classroom', {
      headers: { 'x-openmaic-internal-token': 'service-secret' },
    });
    const invalid = new Request('http://localhost/api/generate-classroom', {
      headers: { 'x-openmaic-internal-token': 'wrong-secret' },
    });

    expect(isInternalRequest(valid, 'service-secret')).toBe(true);
    expect(isInternalRequest(invalid, 'service-secret')).toBe(false);
    expect(isInternalRequest(valid, '')).toBe(false);
  });

  it('verifies a playback token only before its expiry', async () => {
    const secret = 'playback-secret';
    const expiresAt = 2_000_000_000;
    const token = await buildPlaybackToken('room_123', expiresAt, secret);

    await expect(verifyPlaybackToken(token, secret, 'room_123', expiresAt - 1)).resolves.toBe(true);
    await expect(verifyPlaybackToken(token, secret, 'room_456', expiresAt - 1)).resolves.toBe(
      false,
    );
    await expect(verifyPlaybackToken(token, secret, 'room_123', expiresAt + 1)).resolves.toBe(
      false,
    );
    await expect(
      verifyPlaybackToken(`room_123.${expiresAt}.bad`, secret, 'room_123', expiresAt - 1),
    ).resolves.toBe(false);
  });
});
