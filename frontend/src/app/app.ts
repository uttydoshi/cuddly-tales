import { DOCUMENT } from '@angular/common';
import { Component, DestroyRef, inject, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { NavigationEnd, Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { filter, map, startWith } from 'rxjs';

import { Footer } from './shared/footer';
import { ShellService } from './shared/shell.service';

/** Which bottom tab a URL belongs to (0-3), or -1 when none does. */
export function tabIndexFor(url: string): number {
  const path = url.split(/[?#]/)[0];
  const tabs = ['/new', '/stories', '/characters', '/profile'];
  return tabs.findIndex((tab) => path === tab || path.startsWith(tab + '/'));
}

@Component({
  imports: [RouterOutlet, RouterLink, RouterLinkActive, Footer],
  selector: 'app-root',
  styleUrl: './app.css',
  templateUrl: './app.html',
})
export class App {
  protected readonly shell = inject(ShellService);
  private readonly router = inject(Router);
  private readonly document = inject(DOCUMENT);

  /** The current tab, for the sliding lens in the phone tab bar. */
  protected readonly tabIndex = toSignal(
    this.router.events.pipe(
      filter((event) => event instanceof NavigationEnd),
      map(() => tabIndexFor(this.router.url)),
      startWith(tabIndexFor(this.router.url)),
    ),
    { initialValue: -1 },
  );

  /** True while the dark footer is behind the tab bar, so the bar turns to dark glass. */
  protected readonly tabsOverDark = signal(false);

  constructor() {
    const view = this.document.defaultView;
    let frame = 0;
    const check = () => {
      frame = 0;
      const footer = this.document.querySelector('app-footer');
      const height = view?.innerHeight ?? 0;
      // The bar's middle sits about 3rem above the bottom edge.
      this.tabsOverDark.set(!!footer && footer.getBoundingClientRect().top < height - 48);
    };
    const schedule = () => {
      if (!frame) {
        frame = view?.requestAnimationFrame(check) ?? 0;
      }
    };
    view?.addEventListener('scroll', schedule, { passive: true });
    view?.addEventListener('resize', schedule, { passive: true });
    const sub = this.router.events
      .pipe(filter((event) => event instanceof NavigationEnd))
      .subscribe(() => view?.setTimeout(schedule, 50));
    inject(DestroyRef).onDestroy(() => {
      view?.removeEventListener('scroll', schedule);
      view?.removeEventListener('resize', schedule);
      sub.unsubscribe();
    });
  }
}
