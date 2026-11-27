import { fromLines, toLines } from './lines';

describe('lines', () => {
  it('splits text into trimmed, non-empty lines', () => {
    expect(toLines('  brave \n\n  yawns a lot\n   \n')).toEqual(['brave', 'yawns a lot']);
  });

  it('returns an empty list for blank text', () => {
    expect(toLines('   \n  ')).toEqual([]);
  });

  it('round-trips a list', () => {
    expect(toLines(fromLines(['a', 'b']))).toEqual(['a', 'b']);
  });
});
