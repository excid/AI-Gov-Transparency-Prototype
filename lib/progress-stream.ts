export type ProgressEvent =
  | { type: 'progress'; stage: string; percent: number }
  | { type: 'result'; data: unknown }
  | { type: 'error'; message: string };

export function decodeProgressLines() {
  let pending = '';
  function decode(completeOnly: boolean): ProgressEvent[] {
    const lines = pending.split('\n');
    pending = completeOnly ? '' : (lines.pop() ?? '');
    try {
      return lines.filter(Boolean).map((line) => JSON.parse(line) as ProgressEvent);
    } catch {
      throw new Error('Invalid progress stream');
    }
  }
  return {
    push(chunk: string) {
      pending += chunk;
      return decode(false);
    },
    finish() {
      if (pending.trim()) pending += '\n';
      return decode(true);
    },
  };
}
