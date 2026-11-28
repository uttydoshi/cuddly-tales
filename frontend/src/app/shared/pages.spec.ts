import { clampPage, countPages, edgeTap, loadPlace, pageAt, placeOf, savePlace, swipeTurn } from './pages';

describe('reading in pages', () => {
  it('counts pages from where the content ends', () => {
    // Pages are 400px wide with a 48px gap: each page starts 448px after the last.
    expect(countPages(0, 448)).toBe(1); // everything on the cover
    expect(countPages(390, 448)).toBe(1); // ends near the right of the first page
    expect(countPages(448, 448)).toBe(2); // ends right at the start of the second
    expect(countPages(448 * 6 + 120, 448)).toBe(7);
    expect(countPages(387 * 6 - 1, 387)).toBe(7); // drawn a pixel early (seen in Chrome): still page 7
    expect(countPages(500, 0)).toBe(1);
  });

  it('keeps the page in range', () => {
    expect(clampPage(-1, 5)).toBe(0);
    expect(clampPage(9, 5)).toBe(4);
    expect(clampPage(2, 0)).toBe(0);
  });

  it('keeps your place when the pages are laid out again', () => {
    // Halfway through 9 pages is halfway through 5 pages after the text gets bigger.
    expect(pageAt(placeOf(4, 9), 5)).toBe(2);
    expect(pageAt(placeOf(8, 9), 12)).toBe(11); // the last page stays the last page
    expect(pageAt(placeOf(0, 9), 12)).toBe(0); // and the cover stays the cover
    expect(placeOf(3, 1)).toBe(0);
  });

  it('turns the page from a tap on either edge, not the middle', () => {
    expect(edgeTap(20, 400)).toBe(-1);
    expect(edgeTap(200, 400)).toBe(0);
    expect(edgeTap(390, 400)).toBe(1);
  });

  it('turns the page on a sideways swipe only', () => {
    expect(swipeTurn(-120, 10)).toBe(1);
    expect(swipeTurn(120, -5)).toBe(-1);
    expect(swipeTurn(-20, 0)).toBe(0); // too short
    expect(swipeTurn(-80, 120)).toBe(0); // scrolling up and down, not turning
  });

  it('remembers the place per story', () => {
    savePlace(41, 0.5);
    expect(loadPlace(41)).toBe(0.5);
    expect(loadPlace(42)).toBe(0);
  });
});
