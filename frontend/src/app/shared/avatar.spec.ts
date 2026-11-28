import { PLACEHOLDER_COLOURS, avatarSrc, initial, placeholderColour } from './avatar';

describe('avatar helpers', () => {
  it('finds the drawn avatar for the seed cast, whatever the case', () => {
    expect(avatarSrc('Minnie')).toBe('/avatars/minnie.svg');
    expect(avatarSrc(' the big bad wolf ')).toBe('/avatars/big-bad-wolf.svg');
    expect(avatarSrc('Eight')).toBe('/avatars/eight.svg');
  });

  it('has no drawn avatar for a character a parent adds', () => {
    expect(avatarSrc('Bela')).toBeNull();
  });

  it('gives the same name the same pastel colour', () => {
    expect(placeholderColour('Nani')).toBe(placeholderColour('nani '));
    expect(PLACEHOLDER_COLOURS).toContain(placeholderColour('Nani'));
  });

  it('uses the first letter, skipping a leading "The"', () => {
    expect(initial('bela')).toBe('B');
    expect(initial('The Snow Fox')).toBe('S');
    expect(initial('The')).toBe('T');
  });
});
