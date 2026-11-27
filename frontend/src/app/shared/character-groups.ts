import { Character, CharacterType } from '../models';

export const CHARACTER_GROUPS: { type: CharacterType; label: string }[] = [
  { type: 'family', label: 'Family' },
  { type: 'original', label: 'Friends' },
  { type: 'folklore', label: 'Folk tales' },
  { type: 'latte_monster', label: 'Latte monsters' },
  { type: 'custom', label: 'Your characters' },
];

/** Groups in a fixed order, leaving out empty ones. */
export function groupByType(characters: Character[]) {
  return CHARACTER_GROUPS.map((group) => ({
    ...group,
    characters: characters.filter((c) => c.type === group.type),
  })).filter((group) => group.characters.length > 0);
}
