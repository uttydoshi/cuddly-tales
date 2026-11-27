import { DatePipe } from '@angular/common';
import { Component, effect, inject, input, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';

import { Story } from '../../models';
import { ApiService } from '../../services/api.service';
import { ConfirmDelete } from '../../shared/confirm-delete';
import { StoryText } from '../../story-text/story-text';

@Component({
  selector: 'app-story-detail',
  imports: [RouterLink, StoryText, ReactiveFormsModule, ConfirmDelete, DatePipe],
  templateUrl: './story-detail.html',
  styleUrl: './story-detail.css',
})
export class StoryDetail {
  private readonly api = inject(ApiService);
  private readonly router = inject(Router);

  /** Bound from the :id route parameter. */
  readonly id = input.required<string>();
  readonly story = signal<Story | null>(null);
  readonly notFound = signal(false);
  readonly actionError = signal('');
  readonly editing = signal(false);
  readonly busy = signal(false);

  readonly form = inject(FormBuilder).nonNullable.group({
    title: ['', [Validators.required, Validators.maxLength(120)]],
    text: ['', [Validators.required]],
  });

  constructor() {
    effect((onCleanup) => {
      this.story.set(null);
      this.notFound.set(false);
      this.editing.set(false);
      const sub = this.api.getStory(Number(this.id())).subscribe({
        next: (story) => this.story.set(story),
        error: () => this.notFound.set(true),
      });
      onCleanup(() => sub.unsubscribe());
    });
  }

  names(story: Story): string {
    return story.characters.map((c) => c.name).join(', ') || 'no characters';
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

  setRead(story: Story, read: boolean): void {
    this.update(story, { read });
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

  private update(story: Story, changes: { title?: string; text?: string; read?: boolean }, done?: () => void): void {
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
}
