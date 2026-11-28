import { Component, computed, input } from '@angular/core';

import { CharacterType } from '../models';

/** Hand-drawn badges for the seed cast (and Eight the octopus, Bela the elephant), in public/avatars. Matched by name. */
const SEED_AVATARS: Record<string, string> = {
  minnie: 'minnie',
  maverick: 'maverick',
  tosia: 'tosia',
  diggles: 'diggles',
  'baba yaga': 'baba-yaga',
  'red riding hood': 'red-riding-hood',
  'the gingerbread man': 'gingerbread-man',
  'the big bad wolf': 'big-bad-wolf',
  'the clever monkey': 'clever-monkey',
  'the crocodile': 'crocodile',
  eight: 'eight',
  bela: 'bela',
};

/** Pastel backgrounds for characters a parent adds. */
export const PLACEHOLDER_COLOURS = ['#cfe3ff', '#ffe0cc', '#d9f2c7', '#ffd9e8', '#e6dcff', '#fff1bf', '#ccf2ef', '#ffe0d2'];

/** The drawn avatar's address, or null when the character has none. */
export function avatarSrc(name: string): string | null {
  const file = SEED_AVATARS[name.trim().toLowerCase()];
  return file ? `/avatars/${file}.svg` : null;
}

/** The same name always gets the same colour. */
export function placeholderColour(name: string): string {
  let hash = 0;
  for (const char of name.trim().toLowerCase()) {
    hash = (hash * 31 + char.codePointAt(0)!) >>> 0;
  }
  return PLACEHOLDER_COLOURS[hash % PLACEHOLDER_COLOURS.length];
}

/** First letter, skipping a leading "The" ("The Snow Fox" shows S). */
export function initial(name: string): string {
  const words = name.trim().split(/\s+/);
  const word = words.length > 1 && words[0].toLowerCase() === 'the' ? words[1] : words[0];
  return ([...(word ?? '')][0] ?? '?').toUpperCase();
}

/**
 * A round character badge: the drawn one for the seed cast, otherwise a pastel circle with
 * the first letter and a small badge for the kind of character. Decorative: the name is
 * always written next to it, so screen readers skip it.
 */
@Component({
  selector: 'app-avatar',
  host: { '[style.--size]': 'size() + "px"', 'aria-hidden': 'true' },
  template: `
    @if (src(); as src) {
      <img [src]="src" alt="" [width]="size()" [height]="size()" />
    } @else {
      <svg viewBox="0 0 120 120">
        <circle cx="60" cy="60" r="58" [attr.fill]="colour()" />
        <text x="60" y="80" text-anchor="middle" class="letter">{{ letter() }}</text>
        @if (showBadge()) {
          <circle cx="96" cy="96" r="18" fill="#ffffff" stroke="#2b2340" stroke-width="3" />
          @switch (type()) {
            @case ('family') {
              <path d="M96 105 C88 99 87 94 89.5 91.5 C92 89 95 90 96 92.5 C97 90 100 89 102.5 91.5 C105 94 104 99 96 105 Z" fill="#ef4444" />
            }
            @case ('original') {
              <path d="M96 85.5 L99.1 92 L106 92.8 L100.9 97.5 L102.3 104.5 L96 101 L89.7 104.5 L91.1 97.5 L86 92.8 L92.9 92 Z" fill="#f59e0b" />
            }
            @case ('folklore') {
              <path d="M86.5 89 Q91 87 96 90 Q101 87 105.5 89 V103 Q101 101 96 104 Q91 101 86.5 103 Z M96 90 V104" fill="#7c3aed" stroke="#ffffff" stroke-width="1.2" stroke-linejoin="round" />
            }
            @default {
              <path d="M96 86 L98.5 93.5 L106 96 L98.5 98.5 L96 106 L93.5 98.5 L86 96 L93.5 93.5 Z" fill="#b5186f" />
            }
          }
        }
      </svg>
    }
  `,
  styles: `
    :host {
      display: inline-block;
      flex: none;
      width: var(--size);
      height: var(--size);
      line-height: 0;
    }
    img,
    svg {
      width: 100%;
      height: 100%;
    }
    .letter {
      font-family: 'Source Serif 4', Georgia, serif;
      font-size: 56px;
      font-weight: 600;
      fill: #2b2340;
    }
  `,
})
export class Avatar {
  readonly name = input.required<string>();
  readonly type = input<CharacterType>();
  /** Width and height in CSS pixels. */
  readonly size = input(48);

  readonly src = computed(() => avatarSrc(this.name()));
  readonly colour = computed(() => placeholderColour(this.name()));
  readonly letter = computed(() => initial(this.name()));
  /** The kind badge is too small to read on little faces, like the overlapping ones on story cards. */
  readonly showBadge = computed(() => !!this.type() && this.type() !== 'latte_monster' && this.size() >= 40);
}
