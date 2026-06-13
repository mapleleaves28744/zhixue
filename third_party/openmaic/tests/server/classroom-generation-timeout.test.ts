import { describe, expect, test } from 'vitest';

import {
  resolveClassroomSceneConcurrency,
  runClassroomGenerationStep,
} from '@/lib/server/classroom-generation';

describe('classroom generation step timeout', () => {
  test('rejects a stalled scene step instead of waiting forever', async () => {
    const stalled = new Promise<string>(() => undefined);

    await expect(runClassroomGenerationStep('scene content', 10, () => stalled)).rejects.toThrow(
      'scene content timed out after 10ms',
    );
  });

  test('returns a completed scene step result', async () => {
    await expect(runClassroomGenerationStep('scene content', 100, async () => 'ok')).resolves.toBe(
      'ok',
    );
  });
});

describe('classroom scene concurrency', () => {
  test('uses a conservative parallel default', () => {
    expect(resolveClassroomSceneConcurrency(undefined)).toBe(2);
  });

  test('clamps configured concurrency to a safe range', () => {
    expect(resolveClassroomSceneConcurrency('1')).toBe(1);
    expect(resolveClassroomSceneConcurrency('99')).toBe(4);
  });
});
