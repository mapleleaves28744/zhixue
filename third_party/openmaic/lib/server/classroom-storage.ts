import { promises as fs } from 'fs';
import path from 'path';
import type { NextRequest } from 'next/server';
import type { Scene, Stage } from '@/lib/types/stage';

export const CLASSROOMS_DIR = path.join(process.cwd(), 'data', 'classrooms');
export const CLASSROOM_JOBS_DIR = path.join(process.cwd(), 'data', 'classroom-jobs');

async function ensureDir(dir: string) {
  await fs.mkdir(dir, { recursive: true });
}

export async function ensureClassroomsDir() {
  await ensureDir(CLASSROOMS_DIR);
}

export async function ensureClassroomJobsDir() {
  await ensureDir(CLASSROOM_JOBS_DIR);
}

export async function writeJsonFileAtomic(filePath: string, data: unknown) {
  const dir = path.dirname(filePath);
  await ensureDir(dir);

  const tempFilePath = `${filePath}.${process.pid}.${Date.now()}.tmp`;
  const content = JSON.stringify(data, null, 2);
  await fs.writeFile(tempFilePath, content, 'utf-8');
  await fs.rename(tempFilePath, filePath);
}

export function buildRequestOrigin(req: NextRequest): string {
  const configured = process.env.OPENMAIC_PUBLIC_BASE_URL?.trim();
  if (configured) {
    return configured.replace(/\/$/, '');
  }
  return req.headers.get('x-forwarded-host')
    ? `${req.headers.get('x-forwarded-proto') || 'http'}://${req.headers.get('x-forwarded-host')}`
    : req.nextUrl.origin;
}

function rewriteMediaUrl(url: string, publicBase: string): string {
  if (!url || !publicBase) return url;
  return url
    .replace(/^https?:\/\/openmaic(?::\d+)?/i, publicBase)
    .replace(/^https?:\/\/127\.0\.0\.1(?::\d+)?/i, publicBase)
    .replace(/^https?:\/\/localhost(?::\d+)?/i, publicBase);
}

export function rewriteClassroomForPublicAccess(
  classroom: PersistedClassroomData,
): PersistedClassroomData {
  const publicBase = process.env.OPENMAIC_PUBLIC_BASE_URL?.trim().replace(/\/$/, '') || '';
  if (!publicBase) return classroom;

  const scenes = classroom.scenes.map((scene) => ({
    ...scene,
    actions: Array.isArray(scene.actions)
      ? scene.actions.map((action) => {
          if (!action || typeof action !== 'object') return action;
          const audioUrl = (action as { audioUrl?: string }).audioUrl;
          if (!audioUrl) return action;
          return { ...action, audioUrl: rewriteMediaUrl(audioUrl, publicBase) };
        })
      : scene.actions,
  }));

  const stage = {
    ...classroom.stage,
    generatedAgentConfigs: Array.isArray(classroom.stage.generatedAgentConfigs)
      ? classroom.stage.generatedAgentConfigs.map((agent) => ({
          ...agent,
          avatar:
            typeof agent.avatar === 'string' && agent.avatar.startsWith('/')
              ? agent.avatar
              : agent.avatar,
        }))
      : classroom.stage.generatedAgentConfigs,
  };

  return { ...classroom, stage, scenes };
}

export interface PersistedClassroomData {
  id: string;
  stage: Stage;
  scenes: Scene[];
  createdAt: string;
}

export function isValidClassroomId(id: string): boolean {
  return /^[a-zA-Z0-9_-]+$/.test(id);
}

export async function readClassroom(id: string): Promise<PersistedClassroomData | null> {
  const filePath = path.join(CLASSROOMS_DIR, `${id}.json`);
  try {
    const content = await fs.readFile(filePath, 'utf-8');
    return JSON.parse(content) as PersistedClassroomData;
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') {
      return null;
    }
    throw error;
  }
}

export async function persistClassroom(
  data: {
    id: string;
    stage: Stage;
    scenes: Scene[];
  },
  baseUrl: string,
): Promise<PersistedClassroomData & { url: string }> {
  const classroomData: PersistedClassroomData = {
    id: data.id,
    stage: data.stage,
    scenes: data.scenes,
    createdAt: new Date().toISOString(),
  };

  await ensureClassroomsDir();
  const filePath = path.join(CLASSROOMS_DIR, `${data.id}.json`);
  await writeJsonFileAtomic(filePath, classroomData);

  return {
    ...classroomData,
    url: `${baseUrl}/classroom/${data.id}`,
  };
}
