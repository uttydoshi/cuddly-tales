import { DOCUMENT } from '@angular/common';
import { DestroyRef, Injectable, computed, effect, inject, signal } from '@angular/core';

import { ChildProfile } from '../models';
import { ApiService } from '../services/api.service';

export type Theme = 'light' | 'dark';

/** localStorage key for the theme the moon/sun button chose. index.html reads it too. */
export const THEME_KEY = 'cuddly-tales.theme';

const THEME_COLOR: Record<Theme, string> = { light: '#f8fafc', dark: '#0b0b16' };

/**
 * State the app shell shares with pages: the child shown in the top bar, the site's
 * light/dark theme, and reading mode.
 */
@Injectable({ providedIn: 'root' })
export class ShellService {
  private readonly document = inject(DOCUMENT);

  /** The child, shown as "Mira · 3" in the top bar. Pages that change it call setChild. */
  readonly child = signal<ChildProfile | null>(null);

  /** The site's theme. index.html applies it before Angular starts; this starts from what it chose. */
  readonly theme = signal<Theme>(this.document.documentElement.classList.contains('night') ? 'dark' : 'light');

  /** Reading a story: the top bar and tabs step aside, and the page goes into night mode. */
  readonly reading = signal(false);
  /** Night mode while reading. It always starts on; the sun button turns it off for that story. */
  readonly night = signal(true);

  /** Whether the page is dark right now. */
  readonly dark = computed(() => (this.reading() ? this.night() : this.theme() === 'dark'));

  constructor() {
    inject(ApiService)
      .getProfile()
      .subscribe({ next: (child) => this.child.set(child), error: () => undefined });

    effect(() => {
      const dark = this.dark();
      this.document.documentElement.classList.toggle('night', dark);
      this.document
        .querySelector('meta[name="theme-color"]')
        ?.setAttribute('content', THEME_COLOR[dark ? 'dark' : 'light']);
    });

    // Until the parent picks a theme, follow the device when its setting changes.
    const deviceDark = this.document.defaultView?.matchMedia?.('(prefers-color-scheme: dark)');
    const onDeviceChange = (event: MediaQueryListEvent) => {
      if (!readSavedTheme()) {
        this.theme.set(event.matches ? 'dark' : 'light');
      }
    };
    deviceDark?.addEventListener('change', onDeviceChange);
    inject(DestroyRef).onDestroy(() => deviceDark?.removeEventListener('change', onDeviceChange));
  }

  setChild(child: ChildProfile): void {
    this.child.set(child);
  }

  /** The moon/sun button in the top bar. The choice is remembered on this device. */
  toggleTheme(): void {
    const next: Theme = this.theme() === 'dark' ? 'light' : 'dark';
    this.theme.set(next);
    try {
      localStorage.setItem(THEME_KEY, next);
    } catch {
      // Storage blocked (private browsing): the toggle still works for this visit.
    }
  }

  startReading(): void {
    this.night.set(true);
    this.reading.set(true);
  }

  stopReading(): void {
    this.reading.set(false);
  }
}

function readSavedTheme(): Theme | null {
  try {
    const saved = localStorage.getItem(THEME_KEY);
    return saved === 'light' || saved === 'dark' ? saved : null;
  } catch {
    return null;
  }
}
