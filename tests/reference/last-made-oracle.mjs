// Test-only harness. The implementation is imported unchanged from the reference image.
import { readFileSync } from 'node:fs';
import { resolveLastMadeTimestamp } from '/reference/dist/lib/last-made.js';

const cases = JSON.parse(readFileSync(process.argv[2], 'utf8'));
const results = cases.map((item) => {
  try {
    return {
      ...item,
      expected: resolveLastMadeTimestamp(item.input === null ? undefined : item.input, new Date(item.now)),
    };
  } catch (error) {
    return { ...item, error: error.message };
  }
});
process.stdout.write(JSON.stringify(results));
