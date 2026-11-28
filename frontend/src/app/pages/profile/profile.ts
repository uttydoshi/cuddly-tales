import { HttpErrorResponse } from '@angular/common/http';
import { Component, computed, inject, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';

import { ApiService } from '../../services/api.service';
import { ShellService } from '../../shared/shell.service';
import { fromLines, toLines } from '../../shared/lines';

@Component({
  selector: 'app-profile',
  imports: [ReactiveFormsModule],
  templateUrl: './profile.html',
  styleUrl: './profile.css',
})
export class Profile {
  private readonly api = inject(ApiService);
  private readonly shell = inject(ShellService);

  readonly ages = [2, 3, 4, 5, 6];
  readonly loading = signal(true);
  readonly saving = signal(false);
  readonly saved = signal(false);
  readonly errorMessage = signal('');
  /** The name as last saved, so a change can be explained before saving. */
  readonly savedName = signal('');
  readonly storiesRenamed = signal(0);

  readonly form = inject(FormBuilder).nonNullable.group({
    name: ['', [Validators.required, Validators.maxLength(40)]],
    age: [3, [Validators.required, Validators.min(2), Validators.max(6)]],
    favouriteThings: [''],
  });

  private readonly typedName = toSignal(this.form.controls.name.valueChanges, { initialValue: '' });
  /** Set when the parent has typed a different name: stories will change to it on save. */
  readonly renaming = computed(() => {
    const typed = this.typedName().trim();
    return typed && this.savedName() && typed !== this.savedName() ? typed : '';
  });

  constructor() {
    this.api.getProfile().subscribe({
      next: (child) => {
        this.form.setValue({
          name: child.name,
          age: child.age,
          favouriteThings: fromLines(child.favourite_things),
        });
        this.savedName.set(child.name);
        this.loading.set(false);
      },
      error: () => {
        this.errorMessage.set('Could not load the profile. Please check your connection and try again.');
        this.loading.set(false);
      },
    });
    this.form.valueChanges.subscribe(() => this.saved.set(false));
  }

  save(): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    const { name, age, favouriteThings } = this.form.getRawValue();
    const favourites = toLines(favouriteThings);
    if (favourites.length > 10) {
      this.errorMessage.set('Use up to 10 favourite things.');
      return;
    }

    this.saving.set(true);
    this.errorMessage.set('');
    this.api.updateProfile({ name: name.trim(), age: Number(age), favourite_things: favourites }).subscribe({
      next: (child) => {
        this.shell.setChild(child); // the top bar shows the new name and age
        this.savedName.set(child.name);
        this.storiesRenamed.set(child.stories_renamed);
        this.saving.set(false);
        this.saved.set(true);
      },
      error: (error: HttpErrorResponse) => {
        this.saving.set(false);
        this.errorMessage.set(
          error.status === 422
            ? 'Check the fields: the name can be up to 40 characters, and each favourite thing up to 200.'
            : 'Could not save the profile. Please try again.',
        );
      },
    });
  }
}
