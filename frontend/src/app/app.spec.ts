import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { App, tabIndexFor } from './app';

describe('App', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [App],
      providers: [provideRouter([])],
    }).compileComponents();
  });

  it('shows the main pages in the tab bar', async () => {
    const fixture = TestBed.createComponent(App);
    await fixture.whenStable();
    const links = Array.from(
      (fixture.nativeElement as HTMLElement).querySelectorAll('nav.tabs a'),
    ).map((a) => a.textContent?.trim());
    expect(links).toEqual(['New story', 'Stories', 'Characters', 'Your child']);
  });
});

describe('tabIndexFor', () => {
  it('maps pages to their bottom tab, and others to none', () => {
    expect(tabIndexFor('/new')).toBe(0);
    expect(tabIndexFor('/stories')).toBe(1);
    expect(tabIndexFor('/stories?x=1')).toBe(1);
    expect(tabIndexFor('/characters/3/edit')).toBe(2);
    expect(tabIndexFor('/profile')).toBe(3);
    expect(tabIndexFor('/newsletter')).toBe(-1);
    expect(tabIndexFor('/')).toBe(-1);
  });
});
