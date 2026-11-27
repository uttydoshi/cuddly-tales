import { countWords, friendlyDate, joinNames, toParagraphs } from './story-format';

describe('toParagraphs', () => {
  it('splits on blank lines and drops empty ones', () => {
    expect(toParagraphs('One.\n\nTwo,\nstill two.\n\n\n  \nThree.')).toEqual(['One.', 'Two,\nstill two.', 'Three.']);
  });

  it('keeps a paragraph that is still streaming in', () => {
    expect(toParagraphs('The sun went down.\n\nMira wa')).toEqual(['The sun went down.', 'Mira wa']);
  });
});

describe('joinNames', () => {
  it('reads like a sentence', () => {
    expect(joinNames(['Minnie'])).toBe('Minnie');
    expect(joinNames(['Minnie', 'Maverick'])).toBe('Minnie and Maverick');
    expect(joinNames(['Minnie', 'Maverick', 'Tosia'])).toBe('Minnie, Maverick and Tosia');
    expect(joinNames([])).toBe('');
  });
});

describe('friendlyDate', () => {
  const now = new Date(2026, 10, 27, 20, 0); // 27 Nov 2026, 8pm local time

  it('says Today and Yesterday', () => {
    expect(friendlyDate(new Date(2026, 10, 27, 19, 0).toISOString(), now)).toBe('Today');
    expect(friendlyDate(new Date(2026, 10, 26, 19, 0).toISOString(), now)).toBe('Yesterday');
  });

  it('gives a short date for older stories', () => {
    expect(friendlyDate(new Date(2026, 10, 24, 19, 0).toISOString(), now)).toMatch(/24 Nov/);
  });
});

describe('countWords', () => {
  it('counts words, not spaces', () => {
    expect(countWords('  Once upon\n\na time. ')).toBe(4);
    expect(countWords('   ')).toBe(0);
  });
});
