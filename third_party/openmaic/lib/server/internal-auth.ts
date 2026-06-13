const INTERNAL_HEADER = 'x-openmaic-internal-token';

function constantTimeEqual(left: string, right: string): boolean {
  if (!left || left.length !== right.length) return false;
  let mismatch = 0;
  for (let index = 0; index < left.length; index += 1) {
    mismatch |= left.charCodeAt(index) ^ right.charCodeAt(index);
  }
  return mismatch === 0;
}

function bytesToHex(buffer: ArrayBuffer): string {
  return Array.from(new Uint8Array(buffer))
    .map((byte) => byte.toString(16).padStart(2, '0'))
    .join('');
}

async function sign(value: string, secret: string): Promise<string> {
  const encoder = new TextEncoder();
  const key = await crypto.subtle.importKey(
    'raw',
    encoder.encode(secret),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign'],
  );
  return bytesToHex(await crypto.subtle.sign('HMAC', key, encoder.encode(value)));
}

export function isInternalRequest(
  request: Pick<Request, 'headers'>,
  configuredToken = process.env.OPENMAIC_INTERNAL_TOKEN || '',
): boolean {
  const received = request.headers.get(INTERNAL_HEADER) || '';
  return constantTimeEqual(received, configuredToken);
}

export async function buildPlaybackToken(
  classroomId: string,
  expiresAtSeconds: number,
  secret: string,
): Promise<string> {
  if (!secret) throw new Error('OPENMAIC_SIGNING_SECRET is required');
  const expiry = String(Math.floor(expiresAtSeconds));
  return `${classroomId}.${expiry}.${await sign(`${classroomId}:${expiry}`, secret)}`;
}

export async function verifyPlaybackToken(
  token: string,
  secret: string,
  expectedClassroomId?: string,
  nowSeconds = Math.floor(Date.now() / 1000),
): Promise<boolean> {
  if (!token || !secret) return false;
  const [classroomId, expiry, signature, extra] = token.split('.');
  if (!classroomId || !expiry || !signature || extra) return false;
  if (expectedClassroomId && !constantTimeEqual(classroomId, expectedClassroomId)) return false;
  const expiryNumber = Number(expiry);
  if (!Number.isSafeInteger(expiryNumber) || expiryNumber < nowSeconds) return false;
  const expected = await sign(`${classroomId}:${expiry}`, secret);
  return constantTimeEqual(signature, expected);
}
