import { Component, effect, inject, input, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import { Story } from '../../models';
import { ApiService } from '../../services/api.service';
import { StoryText } from '../../story-text/story-text';

@Component({
  selector: 'app-story-detail',
  imports: [RouterLink, StoryText],
  templateUrl: './story-detail.html',
  styleUrl: './story-detail.css',
})
export class StoryDetail {
  private readonly api = inject(ApiService);

  /** Bound from the :id route parameter. */
  readonly id = input.required<string>();
  readonly story = signal<Story | null>(null);
  readonly errorMessage = signal('');

  constructor() {
    effect((onCleanup) => {
      this.story.set(null);
      this.errorMessage.set('');
      const sub = this.api.getStory(Number(this.id())).subscribe({
        next: (story) => this.story.set(story),
        error: () => this.errorMessage.set('That story could not be found.'),
      });
      onCleanup(() => sub.unsubscribe());
    });
  }

  names(story: Story): string {
    return story.characters.map((c) => c.name).join(', ');
  }
}
