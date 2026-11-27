import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, computed, inject, input, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';

import { CharacterInput, CharacterType } from '../../models';
import { ApiService } from '../../services/api.service';
import { Avatar } from '../../shared/avatar';
import { fromLines, toLines } from '../../shared/lines';

/** Types a parent can choose. Latte monsters come from the photo creator. */
const EDITABLE_TYPES: { value: CharacterType; label: string }[] = [
  { value: 'custom', label: 'Your character' },
  { value: 'family', label: 'Family (people and pets)' },
  { value: 'original', label: 'Friend' },
  { value: 'folklore', label: 'Folk tale' },
];

@Component({
  selector: 'app-character-form',
  imports: [ReactiveFormsModule, RouterLink, Avatar],
  templateUrl: './character-form.html',
  styleUrl: './character-form.css',
})
export class CharacterForm implements OnInit {
  private readonly api = inject(ApiService);
  private readonly router = inject(Router);

  /** Bound from the :id route parameter; absent when adding a new character. */
  readonly id = input<string>();

  readonly types = EDITABLE_TYPES;
  readonly loading = signal(false);
  readonly saving = signal(false);
  readonly errorMessage = signal('');
  /** Latte monsters keep their type; the select is hidden for them. */
  readonly isLatteMonster = signal(false);

  readonly form = inject(FormBuilder).nonNullable.group({
    name: ['', [Validators.required, Validators.maxLength(60)]],
    type: ['custom' as CharacterType, Validators.required],
    description: ['', [Validators.required, Validators.minLength(15), Validators.maxLength(500)]],
    traits: [''],
    rules: [''],
  });

  /** The form as it is typed, for the live avatar preview. */
  readonly value = toSignal(this.form.valueChanges, { initialValue: this.form.getRawValue() });
  readonly previewName = computed(() => this.value().name?.trim() || '?');

  ngOnInit(): void {
    const id = this.id();
    if (!id) {
      return;
    }
    this.loading.set(true);
    this.api.getCharacter(Number(id)).subscribe({
      next: (character) => {
        this.isLatteMonster.set(character.type === 'latte_monster');
        this.form.setValue({
          name: character.name,
          type: character.type,
          description: character.description,
          traits: fromLines(character.traits),
          rules: fromLines(character.rules),
        });
        this.loading.set(false);
      },
      error: () => {
        this.errorMessage.set('That character could not be found.');
        this.loading.set(false);
      },
    });
  }

  save(): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    const value = this.form.getRawValue();
    const traits = toLines(value.traits);
    const rules = toLines(value.rules);
    if (traits.length > 10 || rules.length > 10) {
      this.errorMessage.set('Use up to 10 traits and up to 10 rules.');
      return;
    }
    const character: CharacterInput = {
      name: value.name.trim(),
      type: value.type,
      description: value.description.trim(),
      traits,
      rules,
    };

    const id = this.id();
    const { type, ...withoutType } = character;
    const request = id
      ? this.api.updateCharacter(Number(id), this.isLatteMonster() ? withoutType : character)
      : this.api.createCharacter(character);

    this.saving.set(true);
    this.errorMessage.set('');
    request.subscribe({
      next: () => this.router.navigate(['/characters']),
      error: (error: HttpErrorResponse) => {
        this.saving.set(false);
        this.errorMessage.set(
          error.status === 422
            ? 'Some fields are too long or empty. Each trait and rule can be up to 200 characters.'
            : 'Could not save the character. Please try again.',
        );
      },
    });
  }
}
