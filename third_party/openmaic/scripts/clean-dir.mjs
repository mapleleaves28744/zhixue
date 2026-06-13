import { rmSync } from 'node:fs';

const target = process.argv[2];

if (!target) {
  throw new Error('Usage: node clean-dir.mjs <directory>');
}

rmSync(target, { recursive: true, force: true });
