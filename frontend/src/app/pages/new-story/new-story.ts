import { HttpErrorResponse } from '@angular/common/http';
import { Component, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Router, RouterLink } from '@angular/router';

import { Character } from '../../models';
import { ApiService } from '../../services/api.service';
import { groupByType } from '../../shared/character-groups';
import { joinNames } from '../../shared/story-format';
import { ShellService } from '../../shared/shell.service';

export const MAX_FRIENDS = 6;

/** Evenings (6pm to 6am) start on Bedtime; days start on Anytime. Either can be switched. */
export function isEvening(now: Date = new Date()): boolean {
  const hour = now.getHours();
  return hour >= 18 || hour < 6;
}

/** Pick the cast and when the story is for. Writing and reading happen on the story page. */
@Component({
  selector: 'app-new-story',
  imports: [RouterLink],
  templateUrl: './new-story.html',
  styleUrl: './new-story.css',
})
export class NewStory {
  private readonly api = inject(ApiService);
  private readonly router = inject(Router);
  protected readonly shell = inject(ShellService);

  readonly maxFriends = MAX_FRIENDS;
  readonly loading = signal(true);
  readonly starting = signal(false);
  readonly characters = signal<Character[]>([]);
  readonly selected = signal<ReadonlySet<number>>(new Set());
  readonly bedtime = signal(isEvening());
  readonly errorMessage = signal('');
  /** A short nudge when the pen button is tapped before anyone is picked. */
  readonly hint = signal('');
  private hintTimer?: ReturnType<typeof setTimeout>;

  readonly groups = computed(() => groupByType(this.characters()));
  readonly count = computed(() => this.selected().size);
  readonly full = computed(() => this.count() >= MAX_FRIENDS);
  /** "Minnie, Maverick and Tosia", in the order they were picked. */
  readonly chosenNames = computed(() => {
    const byId = new Map(this.characters().map((c) => [c.id, c.name]));
    return joinNames([...this.selected()].map((id) => byId.get(id) ?? '').filter(Boolean));
  });
  readonly buttonLabel = computed(() => {
    const n = this.count();
    if (n === 0) {
      return 'Pick at least one friend';
    }
    return `Write the story with ${n} ${n === 1 ? 'friend' : 'friends'}`;
  });

  constructor() {
    this.api
      .listCharacters()
      .pipe(takeUntilDestroyed())
      .subscribe({
        next: (characters) => {
          this.characters.set(characters);
          this.loading.set(false);
        },
        error: () => {
          this.errorMessage.set('Could not load the characters. Please check your connection and try again.');
          this.loading.set(false);
        },
      });
  }

  toggle(id: number): void {
    const next = new Set(this.selected());
    if (next.has(id)) {
      next.delete(id);
    } else if (next.size < MAX_FRIENDS) {
      next.add(id);
    }
    this.selected.set(next);
  }

  /** The pen button on phones: always visible, greyed out until a friend is picked. */
  pressWrite(): void {
    if (this.starting()) {
      return;
    }
    if (this.count() === 0) {
      this.hint.set('Pick at least one friend first.');
      clearTimeout(this.hintTimer);
      this.hintTimer = setTimeout(() => this.hint.set(''), 2500);
      return;
    }
    this.generate();
  }

  generate(): void {
    this.hint.set('');
    this.starting.set(true);
    this.errorMessage.set('');
    this.api.createStory([...this.selected()], this.bedtime()).subscribe({
      // The story page starts the stream when it's opened this way (and only then).
      next: (story) => this.router.navigate(['/stories', story.id], { state: { stream: true } }),
      error: (error: HttpErrorResponse) => {
        this.starting.set(false);
        this.errorMessage.set(
          error.status === 429 && error.error?.detail
            ? error.error.detail
            : 'Could not start the story. Please try again.',
        );
      },
    });
  }
}
