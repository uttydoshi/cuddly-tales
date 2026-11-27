import { Component, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';

import { StorySummary } from '../../models';
import { ApiService } from '../../services/api.service';
import { Avatar } from '../../shared/avatar';
import { friendlyDate, joinNames } from '../../shared/story-format';

type Filter = 'all' | 'unread' | 'read';

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
      unread: all.filter((s) => s.status !== 'read').length,
      read: all.filter((s) => s.status === 'read').length,
    };
  });

  readonly cards = computed<StoryCard[]>(() =>
    (this.stories() ?? [])
      .filter((s) => this.filter() === 'all' || (this.filter() === 'read') === (s.status === 'read'))
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
