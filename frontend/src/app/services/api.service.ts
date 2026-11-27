import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { Character, CharacterInput, ChildProfile, Story, StorySummary } from '../models';

@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly http = inject(HttpClient);

  getProfile(): Observable<ChildProfile> {
    return this.http.get<ChildProfile>('/api/profile');
  }

  updateProfile(profile: Omit<ChildProfile, 'id'>): Observable<ChildProfile> {
    return this.http.put<ChildProfile>('/api/profile', profile);
  }

  listCharacters(): Observable<Character[]> {
    return this.http.get<Character[]>('/api/characters');
  }

  getCharacter(id: number): Observable<Character> {
    return this.http.get<Character>(`/api/characters/${id}`);
  }

  createCharacter(character: CharacterInput): Observable<Character> {
    return this.http.post<Character>('/api/characters', character);
  }

  updateCharacter(id: number, changes: Partial<CharacterInput>): Observable<Character> {
    return this.http.patch<Character>(`/api/characters/${id}`, changes);
  }

  deleteCharacter(id: number): Observable<void> {
    return this.http.delete<void>(`/api/characters/${id}`);
  }

  createStory(characterIds: number[], bedtime: boolean): Observable<Story> {
    return this.http.post<Story>('/api/stories', { character_ids: characterIds, bedtime });
  }

  listStories(): Observable<StorySummary[]> {
    return this.http.get<StorySummary[]>('/api/stories');
  }

  getStory(id: number): Observable<Story> {
    return this.http.get<Story>(`/api/stories/${id}`);
  }

  updateStory(
    id: number,
    changes: { title?: string; text?: string; read?: boolean; approve?: boolean },
  ): Observable<Story> {
    return this.http.patch<Story>(`/api/stories/${id}`, changes);
  }

  deleteStory(id: number): Observable<void> {
    return this.http.delete<void>(`/api/stories/${id}`);
  }
}
