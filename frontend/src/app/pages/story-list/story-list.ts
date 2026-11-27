import { DatePipe } from '@angular/common';
import { Component, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';

import { StorySummary } from '../../models';
import { ApiService } from '../../services/api.service';

@Component({
  selector: 'app-story-list',
  imports: [RouterLink, DatePipe],
  templateUrl: './story-list.html',
  styleUrl: './story-list.css',
})
export class StoryList {
  readonly stories = signal<StorySummary[] | null>(null);
  readonly errorMessage = signal('');

  constructor() {
    inject(ApiService)
      .listStories()
      .pipe(takeUntilDestroyed())
      .subscribe({
        next: (stories) => this.stories.set(stories),
        error: () => this.errorMessage.set('Could not load your stories. Is the server running?'),
      });
  }

  names(story: StorySummary): string {
    return story.characters.map((c) => c.name).join(', ');
  }
}
