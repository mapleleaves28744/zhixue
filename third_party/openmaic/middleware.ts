import { NextRequest, NextResponse } from 'next/server';
import { isInternalRequest, verifyPlaybackToken } from '@/lib/server/internal-auth';

/** Convert string to Uint8Array */
function encode(str: string): Uint8Array {
  return new TextEncoder().encode(str);
}

/** Convert ArrayBuffer to hex string */
function bufToHex(buf: ArrayBuffer): string {
  return Array.from(new Uint8Array(buf))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
}

/** Verify an HMAC-signed token using Web Crypto API (Edge-compatible) */
async function verifyToken(token: string, accessCode: string): Promise<boolean> {
  const dotIndex = token.indexOf('.');
  if (dotIndex === -1) return false;

  const timestamp = token.substring(0, dotIndex);
  const signature = token.substring(dotIndex + 1);

  const keyData = encode(accessCode);
  const key = await crypto.subtle.importKey(
    'raw',
    keyData.buffer as ArrayBuffer,
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign'],
  );

  const data = encode(timestamp);
  const expected = bufToHex(await crypto.subtle.sign('HMAC', key, data.buffer as ArrayBuffer));

  // Constant-length comparison (not truly constant-time in JS, but sufficient here)
  if (signature.length !== expected.length) return false;
  let mismatch = 0;
  for (let i = 0; i < signature.length; i++) {
    mismatch |= signature.charCodeAt(i) ^ expected.charCodeAt(i);
  }
  return mismatch === 0;
}

export async function middleware(request: NextRequest) {
  const accessCode = process.env.ACCESS_CODE;
  const signingSecret = process.env.OPENMAIC_SIGNING_SECRET;
  if (!accessCode && !signingSecret) {
    return NextResponse.next();
  }

  const { pathname } = request.nextUrl;

  // Whitelist: access-code endpoints, health check
  if (pathname.startsWith('/api/access-code/') || pathname === '/api/health') {
    return NextResponse.next();
  }

  if (pathname.startsWith('/api/') && isInternalRequest(request)) {
    return NextResponse.next();
  }

  const zhixueToken =
    request.nextUrl.searchParams.get('zhixue_token') ||
    request.cookies.get('openmaic_zhixue_access')?.value ||
    '';
  const classroomPageMatch = pathname.match(/^\/classroom\/([^/]+)$/);
  const classroomMediaMatch = pathname.match(/^\/api\/classroom-media\/([^/]+)\//);
  const requestedClassroomId =
    classroomPageMatch?.[1] ||
    classroomMediaMatch?.[1] ||
    (pathname === '/api/classroom' ? request.nextUrl.searchParams.get('id') : null);
  const signedPlaybackAllowed =
    signingSecret &&
    ((requestedClassroomId &&
      (await verifyPlaybackToken(zhixueToken, signingSecret, requestedClassroomId))) ||
      (!pathname.startsWith('/api/') &&
        !pathname.startsWith('/classroom/') &&
        (await verifyPlaybackToken(zhixueToken, signingSecret))));
  if (signedPlaybackAllowed) {
    const response = NextResponse.next();
    if (request.nextUrl.searchParams.has('zhixue_token')) {
      response.cookies.set('openmaic_zhixue_access', zhixueToken, {
        httpOnly: true,
        sameSite: 'lax',
        secure: process.env.NODE_ENV === 'production',
        path: '/',
      });
    }
    return response;
  }

  // Check legacy access-code cookie — validate HMAC signature, not just existence
  const cookie = request.cookies.get('openmaic_access');
  if (accessCode && cookie?.value && (await verifyToken(cookie.value, accessCode))) {
    return NextResponse.next();
  }

  // API requests without valid cookie → 401
  if (pathname.startsWith('/api/')) {
    return NextResponse.json(
      { success: false, errorCode: 'INVALID_REQUEST', error: 'Access code required' },
      { status: 401 },
    );
  }

  if (signingSecret && !accessCode) {
    return new NextResponse('Signed Zhixue classroom access required', { status: 401 });
  }

  // Legacy access-code pages show the existing modal.
  return NextResponse.next();
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico|logos/).*)'],
};
