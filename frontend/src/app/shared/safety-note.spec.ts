import { safetyNote } from './safety-note';

describe('safetyNote', () => {
  it('says how the check went, with the child’s age', () => {
    expect(safetyNote('passed', 3)).toBe('Checked: gentle for age 3');
    expect(safetyNote('rewritten', 4)).toBe('Checked: rewritten once to be just right for age 4');
    expect(safetyNote('approved', 3)).toBe('Checked: you read it and said it’s fine');
  });

  it('works without an age', () => {
    expect(safetyNote('passed')).toBe('Checked: gentle');
  });

  it('says nothing for flagged or unchecked stories', () => {
    expect(safetyNote('needs_review', 3)).toBe('');
    expect(safetyNote(null, 3)).toBe('');
  });
});
