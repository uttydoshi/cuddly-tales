/** Textarea text, one item per line, to a list: trims each line and drops blank ones. */
export function toLines(text: string): string[] {
  return text
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => line.length > 0);
}

/** A list back to one item per line, for a textarea. */
export function fromLines(items: string[]): string {
  return items.join('\n');
}
