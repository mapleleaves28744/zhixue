import { type NextRequest } from 'next/server';
import { apiError, apiSuccess } from '@/lib/server/api-response';
import { isInternalRequest } from '@/lib/server/internal-auth';
import { isValidClassroomId, readClassroom } from '@/lib/server/classroom-storage';

export const dynamic = 'force-dynamic';

export async function GET(req: NextRequest, context: { params: Promise<{ id: string }> }) {
  if (!isInternalRequest(req)) {
    return apiError('INVALID_REQUEST', 401, 'Invalid internal service token');
  }

  const { id } = await context.params;
  if (!isValidClassroomId(id)) {
    return apiError('INVALID_REQUEST', 400, 'Invalid classroom id');
  }
  const classroom = await readClassroom(id);
  if (!classroom) {
    return apiError('INVALID_REQUEST', 404, 'Classroom not found');
  }
  return apiSuccess({ ...classroom });
}
