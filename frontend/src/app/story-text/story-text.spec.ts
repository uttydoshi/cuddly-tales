import { TestBed } from '@angular/core/testing';

import { StoryText, toParts } from './story-text';

describe('toParts', () => {
  it('marks *word* as italic', () => {
    expect(toParts('A star is *gwiazda* in Polish.')).toEqual([
      { text: 'A star is ', italic: false },
      { text: 'gwiazda', italic: true },
      { text: ' in Polish.', italic: false },
    ]);
  });

  it('leaves an unclosed asterisk as plain text while streaming', () => {
    expect(toParts('A star is *gwia')).toEqual([{ text: 'A star is *gwia', italic: false }]);
  });

  it('returns plain text unchanged', () => {
    expect(toParts('Goodnight.')).toEqual([{ text: 'Goodnight.', italic: false }]);
  });
});

describe('StoryText', () => {
  it('renders italics as <em> and never as raw HTML', async () => {
    const fixture = TestBed.createComponent(StoryText);
    fixture.componentRef.setInput('text', 'Say *gwiazda* <b>now</b>');
    await fixture.whenStable();
    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector('em')?.textContent).toBe('gwiazda');
    expect(el.querySelector('b')).toBeNull();
    expect(el.textContent).toBe('Say gwiazda <b>now</b>');
  });
});
