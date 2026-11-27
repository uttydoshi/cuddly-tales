import { DOCUMENT } from '@angular/common';
import { Injectable, effect, inject, signal } from '@angular/core';

import { ChildProfile } from '../models';
import { ApiService } from '../services/api.service';

/** State the app shell shares with pages: the child shown in the top bar, and reading mode. */
@Injectable({ providedIn: 'root' })
export class ShellService {
  private readonly document = inject(DOCUMENT);

  /** The child, shown as "Mira · 3" in the top bar. Pages that change it call setChild. */
  readonly child = signal<ChildProfile | null>(null);

  /** Reading a story: the top bar and tabs step aside, and the page goes into night mode. */
  readonly reading = signal(false);
  /** Night mode while reading. It always starts on; the sun button turns it off for that story. */
  readonly night = signal(true);

  constructor() {
    inject(ApiService)
      .getProfile()
      .subscribe({ next: (child) => this.child.set(child), error: () => undefined });

    effect(() => {
      this.document.documentElement.classList.toggle('night', this.reading() && this.night());
    });
  }

  setChild(child: ChildProfile): void {
    this.child.set(child);
  }

  startReading(): void {
    this.night.set(true);
    this.reading.set(true);
  }

  stopReading(): void {
    this.reading.set(false);
  }
}
