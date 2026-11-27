import { Component, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import { Character } from '../../models';
import { ApiService } from '../../services/api.service';
import { groupByType } from '../../shared/character-groups';
import { ConfirmDelete } from '../../shared/confirm-delete';

@Component({
  selector: 'app-characters',
  imports: [RouterLink, ConfirmDelete],
  templateUrl: './characters.html',
  styleUrl: './characters.css',
})
export class Characters {
  private readonly api = inject(ApiService);

  readonly characters = signal<Character[] | null>(null);
  readonly errorMessage = signal('');
  readonly groups = computed(() => groupByType(this.characters() ?? []));

  constructor() {
    this.api.listCharacters().subscribe({
      next: (characters) => this.characters.set(characters),
      error: () => this.errorMessage.set('Could not load the characters. Please check your connection and try again.'),
    });
  }

  remove(character: Character): void {
    this.errorMessage.set('');
    this.api.deleteCharacter(character.id).subscribe({
      next: () => this.characters.update((list) => list?.filter((c) => c.id !== character.id) ?? null),
      error: () => this.errorMessage.set(`Could not delete ${character.name}. Please try again.`),
    });
  }
}
