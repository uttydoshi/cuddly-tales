import { Component, computed, input } from '@angular/core';

export interface TextPart {
  text: string;
  italic: boolean;
}

const ITALIC = /\*([^*\n]+)\*/g;

/**
 * Split story text into plain and italic parts. The model marks words from
 * another language (like a Polish word) as *word*. An unclosed asterisk,
 * which happens mid-stream, stays as plain text until its pair arrives.
 */
export function toParts(text: string): TextPart[] {
  const parts: TextPart[] = [];
  let last = 0;
  for (const match of text.matchAll(ITALIC)) {
    if (match.index > last) {
      parts.push({ text: text.slice(last, match.index), italic: false });
    }
    parts.push({ text: match[1], italic: true });
    last = match.index + match[0].length;
  }
  if (last < text.length) {
    parts.push({ text: text.slice(last), italic: false });
  }
  return parts;
}

/** Story text with italics. Rendered as text nodes, never as HTML. */
@Component({
  selector: 'app-story-text',
  template: `@for (part of parts(); track $index) {@if (part.italic) {<em>{{ part.text }}</em>} @else {<span>{{ part.text }}</span>}}`,
  styles: ':host { display: inline; } em { font-style: italic; color: var(--accent); }',
})
export class StoryText {
  readonly text = input.required<string>();
  readonly parts = computed(() => toParts(this.text()));
}
