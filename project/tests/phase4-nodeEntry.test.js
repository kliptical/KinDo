import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const indexPath = path.resolve(__dirname, '../src/index.js');

describe('4.7 node index.js entry point', () => {
  test('runs to completion with exit code 0', async () => {
    const result = await new Promise((resolve, reject) => {
      const child = spawn('node', [indexPath], { stdio: ['ignore', 'pipe', 'pipe'] });
      let stdout = '';
      let stderr = '';
      child.stdout.on('data', d => { stdout += d.toString(); });
      child.stderr.on('data', d => { stderr += d.toString(); });
      child.on('close', code => resolve({ code, stdout, stderr }));
      child.on('error', reject);
      // 30 s safety timeout — kills the child and surfaces a clear failure message.
      setTimeout(
        () => { child.kill('SIGTERM'); resolve({ code: -1, stdout, stderr, timedOut: true }); },
        30000,
      );
    });
    assert.equal(result.timedOut, undefined, 'node index.js timed out: ' + result.stderr);
    assert.equal(result.code, 0, 'exit code: ' + result.code + ' stderr: ' + result.stderr);
    assert.ok(result.stdout.includes('[FTM]'), 'stdout missing [FTM] log line');
  });
});
