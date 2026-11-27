import { HttpErrorResponse } from '@angular/common/http';
import { Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';

import { ApiService } from '../../services/api.service';
import { fromLines, toLines } from '../../shared/lines';

@Component({
  selector: 'app-profile',
  imports: [ReactiveFormsModule],
  templateUrl: './profile.html',
  styleUrl: './profile.css',
})
export class Profile {
  private readonly api = inject(ApiService);

  readonly ages = [2, 3, 4, 5, 6];
  readonly loading = signal(true);
  readonly saving = signal(false);
  readonly saved = signal(false);
  readonly errorMessage = signal('');

  readonly form = inject(FormBuilder).nonNullable.group({
    name: ['', [Validators.required, Validators.maxLength(40)]],
    age: [3, [Validators.required, Validators.min(2), Validators.max(6)]],
    favouriteThings: [''],
  });

  constructor() {
    this.api.getProfile().subscribe({
      next: (child) => {
        this.form.setValue({
          name: child.name,
          age: child.age,
          favouriteThings: fromLines(child.favourite_things),
        });
        this.loading.set(false);
      },
      error: () => {
        this.errorMessage.set('Could not load the profile. Is the server running?');
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
      next: () => {
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
