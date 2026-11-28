import { Component, DestroyRef, computed, effect, inject, input, signal, untracked } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { Subscription } from 'rxjs';

import { Story, StoryChanges } from '../../models';
import { ApiService } from '../../services/api.service';
import { StoryStreamService } from '../../services/story-stream.service';
import { Avatar } from '../../shared/avatar';
import { ConfirmDelete } from '../../shared/confirm-delete';
import { safetyNote } from '../../shared/safety-note';
import { ShellService } from '../../shared/shell.service';
import { countWords, friendlyDate, joinNames, toParagraphs } from '../../shared/story-format';
import { StoryText } from '../../story-text/story-text';

/** Reading text sizes in px; the A buttons step through them. */
export const TEXT_SIZES = [18, 19.5, 21, 23, 25];
const DEFAULT_SIZE_INDEX = 2;
const SIZE_KEY = 'cuddly-tales.text-size';

/** streaming: words arriving (first version or the rewrite). checking: the safety and age check. */
type Writing = 'idle' | 'streaming' | 'checking' | 'failed';

/** Reading a story: full screen, large type, night mode for bedtime stories. Also where a new story streams in. */
@Component({
  selector: 'app-story-detail',
  imports: [RouterLink, Avatar, StoryText, ReactiveFormsModule, ConfirmDelete],
  templateUrl: './story-detail.html',
  styleUrl: './story-detail.css',
})
export class StoryDetail {
  private readonly api = inject(ApiService);
  private readonly streams = inject(StoryStreamService);
  private readonly router = inject(Router);
  protected readonly shell = inject(ShellService);

  /** Bound from the :id route parameter. */
  readonly id = input.required<string>();

  readonly story = signal<Story | null>(null);
  readonly notFound = signal(false);
  readonly writing = signal<Writing>('idle');
  readonly streamed = signal('');
  readonly writeError = signal('');
  readonly actionError = signal('');
  readonly editing = signal(false);
  readonly busy = signal(false);
  readonly sizeIndex = signal(loadSizeIndex());
  /** The check found problems and the story is being rewritten once to fix them. */
  readonly rewriting = signal(false);

  readonly textSize = computed(() => TEXT_SIZES[this.sizeIndex()]);
  readonly cast = computed(() => joinNames(this.story()?.characters.map((c) => c.name) ?? []));

  /** While streaming, the model's first line is "# Title". */
  private readonly streamedTitle = computed(() => {
    const [first] = this.streamed().split('\n', 1);
    return first.startsWith('# ') ? first.slice(2).trim() : '';
  });
  private readonly streamedBody = computed(() => {
    const text = this.streamed();
    if (!text.startsWith('# ')) {
      return text;
    }
    const newline = text.indexOf('\n');
    return newline === -1 ? '' : text.slice(newline + 1);
  });

  /** Showing the text as it streams (and while it's checked), not the saved story. */
  readonly live = computed(() => this.writing() === 'streaming' || this.writing() === 'checking');
  readonly title = computed(() =>
    this.live() ? this.streamedTitle() || 'Writing your story…' : (this.story()?.title ?? ''),
  );
  readonly paragraphs = computed(() => toParagraphs(this.live() ? this.streamedBody() : (this.story()?.text ?? '')));
  /** What the safety check found in the version that was kept (the last one it looked at). */
  readonly problems = computed(() => this.story()?.safety?.attempts.at(-1)?.problems ?? []);
  readonly childName = computed(() => this.shell.child()?.name ?? 'your child');
  readonly checkedNote = computed(() => safetyNote(this.story()?.safety_status, this.shell.child()?.age));
  readonly wordsSoFar = computed(() => countWords(this.streamedBody()));
  /** For a planned adventure night: which night the agent writes next. */
  readonly nextNight = signal<number | null>(null);
  readonly readOn = computed(() => {
    const readAt = this.story()?.read_at;
    return readAt ? friendlyDate(readAt) : '';
  });

  readonly form = inject(FormBuilder).nonNullable.group({
    title: ['', [Validators.required, Validators.maxLength(120)]],
    text: ['', [Validators.required]],
  });

  private stream?: Subscription;
  private wakeLock: { release(): Promise<void> } | null = null;

  constructor() {
    this.shell.startReading();
    inject(DestroyRef).onDestroy(() => {
      this.stream?.unsubscribe();
      this.wakeLock?.release().catch(() => undefined);
      this.shell.stopReading();
    });
    this.keepScreenOn();

    effect((onCleanup) => {
      const id = Number(this.id());
      untracked(() => this.reset());
      const sub = this.api.getStory(id).subscribe({
        next: (story) => {
          this.story.set(story);
          this.shell.readingStory(story.bedtime);
          // Stream only when opened straight from "Write the story", never on a reload,
          // so a refresh can't start a second copy of the same story.
          if (story.status === 'planned' && story.adventure) {
            this.api.getAdventure(story.adventure.id).subscribe((adventure) => {
              this.nextNight.set(adventure.chapters.find((c) => c.status === 'planned')?.night ?? null);
            });
          } else if (story.status === 'planned' && takeStreamFlag()) {
            this.write();
          }
        },
        error: () => this.notFound.set(true),
      });
      onCleanup(() => sub.unsubscribe());
    });
  }

  /** An adventure night is written by the agent, on its own page. */
  writeNight(adventureId: number): void {
    this.busy.set(true);
    this.actionError.set('');
    this.api.writeNextNight(adventureId).subscribe({
      next: (run) => this.router.navigate(['/adventures/runs', run.id]),
      error: (error) => {
        this.busy.set(false);
        this.actionError.set(error.error?.detail ?? 'Could not start writing this night. Please try again.');
      },
    });
  }

  /** Stream the story from the model. Also used for "Write it now" and "Try again". */
  write(): void {
    const story = this.story();
    if (!story) {
      return;
    }
    this.stream?.unsubscribe();
    this.streamed.set('');
    this.writeError.set('');
    this.rewriting.set(false);
    this.writing.set('streaming');
    this.stream = this.streams.stream(story.id).subscribe((event) => {
      if (event.type === 'word') {
        this.streamed.update((text) => text + event.text);
      } else if (event.type === 'checking') {
        this.writing.set('checking');
      } else if (event.type === 'rewriting') {
        // The rewrite streams in place of the first version.
        this.streamed.set('');
        this.rewriting.set(true);
        this.writing.set('streaming');
      } else if (event.type === 'done') {
        // Swap the streamed text for the saved story (title, word count, reading time).
        this.api.getStory(story.id).subscribe({
          next: (saved) => {
            this.story.set(saved);
            this.writing.set('idle');
          },
          error: () => this.writing.set('idle'),
        });
      } else {
        this.writeError.set(event.message);
        this.writing.set('failed');
      }
    });
  }

  smaller(): void {
    this.setSize(this.sizeIndex() - 1);
  }

  larger(): void {
    this.setSize(this.sizeIndex() + 1);
  }

  toggleNight(): void {
    this.shell.night.update((on) => !on);
  }

  startEditing(story: Story): void {
    this.form.setValue({ title: story.title, text: story.text ?? '' });
    this.actionError.set('');
    this.editing.set(true);
  }

  saveEdits(story: Story): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    const { title, text } = this.form.getRawValue();
    // Text can only be edited once the story has been written.
    const changes = story.text === null ? { title } : { title, text };
    this.update(story, changes, () => this.editing.set(false));
  }

  /** The heart: a favourite story shows under Favourites on the stories page. */
  toggleFavourite(story: Story): void {
    this.update(story, { favourite: !story.favourite });
  }

  setRead(story: Story, read: boolean): void {
    this.update(story, { read });
  }

  /** A parent has read a story the check flagged and says it's fine. */
  approve(story: Story): void {
    this.update(story, { approve: true });
  }

  remove(story: Story): void {
    this.busy.set(true);
    this.api.deleteStory(story.id).subscribe({
      next: () => this.router.navigate(['/stories']),
      error: () => {
        this.busy.set(false);
        this.actionError.set('Could not delete the story. Please try again.');
      },
    });
  }

  private update(
    story: Story,
    changes: StoryChanges,
    done?: () => void,
  ): void {
    this.busy.set(true);
    this.actionError.set('');
    this.api.updateStory(story.id, changes).subscribe({
      next: (updated) => {
        this.story.set(updated);
        this.busy.set(false);
        done?.();
      },
      error: () => {
        this.busy.set(false);
        this.actionError.set('Could not save the change. Please try again.');
      },
    });
  }

  private reset(): void {
    this.stream?.unsubscribe();
    this.story.set(null);
    this.notFound.set(false);
    this.editing.set(false);
    this.writing.set('idle');
    this.rewriting.set(false);
    this.streamed.set('');
    this.nextNight.set(null);
  }

  private setSize(index: number): void {
    const clamped = Math.max(0, Math.min(TEXT_SIZES.length - 1, index));
    this.sizeIndex.set(clamped);
    try {
      localStorage.setItem(SIZE_KEY, String(clamped));
    } catch {
      // Storage can be unavailable (private browsing); the size just won't be remembered.
    }
  }

  /** Stop the phone dimming and locking mid-story. Optional: not every browser allows it. */
  private keepScreenOn(): void {
    const wakeLock = (navigator as Navigator & { wakeLock?: { request(type: 'screen'): Promise<{ release(): Promise<void> }> } })
      .wakeLock;
    wakeLock
      ?.request('screen')
      .then((lock) => (this.wakeLock = lock))
      .catch(() => undefined);
  }
}

function loadSizeIndex(): number {
  try {
    const saved = Number(localStorage.getItem(SIZE_KEY));
    return Number.isInteger(saved) && saved >= 0 && saved < TEXT_SIZES.length ? saved : DEFAULT_SIZE_INDEX;
  } catch {
    return DEFAULT_SIZE_INDEX;
  }
}

/** True once if this page was opened with "start streaming"; then forgotten, so reloads don't stream. */
function takeStreamFlag(): boolean {
  const state = history.state as { stream?: boolean } | null;
  if (!state?.stream) {
    return false;
  }
  history.replaceState({ ...state, stream: false }, '');
  return true;
}
