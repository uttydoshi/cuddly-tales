import { Component, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';

import { StorySummary } from '../../models';
import { ApiService } from '../../services/api.service';
import { Avatar } from '../../shared/avatar';
import { friendlyDate, joinNames } from '../../shared/story-format';

type Filter = 'all' | 'unread' | 'read' | 'favourites';

const SHOWS: Record<Filter, (story: StorySummary) => boolean> = {
  all: () => true,
  unread: (s) => s.status !== 'read',
  read: (s) => s.status === 'read',
  favourites: (s) => s.favourite,
};

interface StoryCard {
  story: StorySummary;
  when: string;
  cast: string;
}

@Component({
  selector: 'app-story-list',
  imports: [RouterLink, Avatar],
  templateUrl: './story-list.html',
  styleUrl: './story-list.css',
})
export class StoryList {
  readonly stories = signal<StorySummary[] | null>(null);
  readonly errorMessage = signal('');
  readonly filter = signal<Filter>('all');

  readonly counts = computed(() => {
    const all = this.stories() ?? [];
    return {
      all: all.length,
      unread: all.filter(SHOWS.unread).length,
      read: all.filter(SHOWS.read).length,
      favourites: all.filter(SHOWS.favourites).length,
    };
  });

  readonly cards = computed<StoryCard[]>(() =>
    (this.stories() ?? [])
      .filter(SHOWS[this.filter()])
      .map((story) => ({
        story,
        when: friendlyDate(story.created_at),
        cast: joinNames(story.characters.map((c) => c.name)),
      })),
  );

  constructor() {
    inject(ApiService)
      .listStories()
      .pipe(takeUntilDestroyed())
      .subscribe({
        next: (stories) => this.stories.set(stories),
        error: () => this.errorMessage.set('Could not load your stories. Please check your connection and try again.'),
      });
  }
}
