/**
 * Reading in pages, like an e-reader. The story is laid out by CSS columns, one page-sized
 * column per page; these helpers do the arithmetic around that layout and the gestures.
 */

/** Browsers place columns at fractional pixels, so a page can start a hair before where the
 * arithmetic says (2321px for a page at 2322px). This much leeway absorbs that. */
const SUBPIXEL = 2;

/** How many pages, given where the last bit of content starts and the distance between pages. */
export function countPages(endOffset: number, step: number): number {
  if (step <= 0) {
    return 1;
  }
  return Math.max(1, Math.floor((endOffset + SUBPIXEL) / step) + 1);
}

export function clampPage(page: number, count: number): number {
  return Math.min(Math.max(0, page), Math.max(0, count - 1));
}

/** How far through the story a page is, from 0 (the cover) to 1 (the last page). */
export function placeOf(page: number, count: number): number {
  return count <= 1 ? 0 : clampPage(page, count) / (count - 1);
}

/** The page at the same place after the pages are laid out again (a new text size, a turned phone). */
export function pageAt(place: number, count: number): number {
  return clampPage(Math.round(place * (count - 1)), count);
}

/** Tapping the left or right edge turns the page back or forward; the middle does nothing. */
export function edgeTap(x: number, width: number): -1 | 0 | 1 {
  if (width <= 0) {
    return 0;
  }
  const at = x / width;
  return at < 0.3 ? -1 : at > 0.7 ? 1 : 0;
}

/** A sideways swipe turns the page: right to left goes forward. Short or mostly-up-and-down moves don't. */
export function swipeTurn(dx: number, dy: number, min = 40): -1 | 0 | 1 {
  if (Math.abs(dx) < min || Math.abs(dx) < Math.abs(dy) * 1.5) {
    return 0;
  }
  return dx < 0 ? 1 : -1;
}

const PLACE_KEY = 'cuddly-tales.place.';

/** Where a story was left on this device (0 to 1), so it opens there next time. */
export function loadPlace(storyId: number): number {
  try {
    const value = Number(localStorage.getItem(PLACE_KEY + storyId));
    return Number.isFinite(value) && value >= 0 && value <= 1 ? value : 0;
  } catch {
    return 0;
  }
}

export function savePlace(storyId: number, place: number): void {
  try {
    localStorage.setItem(PLACE_KEY + storyId, place.toFixed(4));
  } catch {
    // Private browsing or storage off: the story opens at the cover next time.
  }
}
