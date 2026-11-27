import { Component, DestroyRef, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';
import { forkJoin, switchMap } from 'rxjs';

import { Character, CharacterType, ChildProfile } from '../../models';
import { ApiService } from '../../services/api.service';
import { StoryStreamService } from '../../services/story-stream.service';
import { StoryText } from '../../story-text/story-text';

type Phase = 'loading' | 'pick' | 'streaming' | 'done' | 'error';

const GROUPS: { type: CharacterType; label: string }[] = [
  { type: 'family', label: 'Family' },
  { type: 'original', label: 'Friends' },
  { type: 'folklore', label: 'Folk tales' },
  { type: 'latte_monster', label: 'Latte monsters' },
  { type: 'custom', label: 'Your characters' },
];

@Component({
  selector: 'app-new-story',
  imports: [RouterLink, StoryText],
  templateUrl: './new-story.html',
  styleUrl: './new-story.css',
})
export class NewStory {
  private readonly api = inject(ApiService);
  private readonly streams = inject(StoryStreamService);
  private readonly destroyRef = inject(DestroyRef);

  readonly phase = signal<Phase>('loading');
  readonly child = signal<ChildProfile | null>(null);
  readonly characters = signal<Character[]>([]);
  readonly selected = signal<ReadonlySet<number>>(new Set());
  readonly streamedText = signal('');
  readonly storyId = signal<number | null>(null);
  readonly errorMessage = signal('');

  readonly groups = computed(() =>
    GROUPS.map((g) => ({ ...g, characters: this.characters().filter((c) => c.type === g.type) })).filter(
      (g) => g.characters.length > 0,
    ),
  );

  /** The model writes "# Title" on the first line; show it as a heading. */
  readonly title = computed(() => {
    const [first] = this.streamedText().split('\n', 1);
    return first.startsWith('# ') ? first.slice(2) : '';
  });
  readonly body = computed(() => {
    const text = this.streamedText();
    return text.startsWith('# ') ? text.slice(text.indexOf('\n') + 1 || text.length).trimStart() : text;
  });

  constructor() {
    forkJoin([this.api.getProfile(), this.api.listCharacters()])
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: ([child, characters]) => {
          this.child.set(child);
          this.characters.set(characters);
          this.phase.set('pick');
        },
        error: () => this.fail('Could not load the characters. Is the server running?'),
      });
  }

  toggle(id: number): void {
    const next = new Set(this.selected());
    if (next.has(id)) {
      next.delete(id);
    } else {
      next.add(id);
    }
    this.selected.set(next);
  }

  generate(): void {
    this.phase.set('streaming');
    this.streamedText.set('');
    this.errorMessage.set('');

    this.api
      .createStory([...this.selected()])
      .pipe(
        switchMap((story) => {
          this.storyId.set(story.id);
          return this.streams.stream(story.id);
        }),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe({
        next: (event) => {
          if (event.type === 'word') {
            this.streamedText.update((text) => text + event.text);
          } else if (event.type === 'done') {
            this.phase.set('done');
          } else {
            this.fail(event.message);
          }
        },
        error: () => this.fail('Could not start the story. Please try again.'),
      });
  }

  startOver(): void {
    this.selected.set(new Set());
    this.streamedText.set('');
    this.storyId.set(null);
    this.phase.set('pick');
  }

  private fail(message: string): void {
    this.errorMessage.set(message);
    this.phase.set('error');
  }
}
