import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import {
  Adventure,
  AdventureRequest,
  AgentRun,
  Character,
  CharacterInput,
  ChildProfile,
  ChildProfileSaved,
  Story,
  StoryChanges,
  StorySummary,
} from '../models';

@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly http = inject(HttpClient);

  getProfile(): Observable<ChildProfile> {
    return this.http.get<ChildProfile>('/api/profile');
  }

  updateProfile(profile: Omit<ChildProfile, 'id'>): Observable<ChildProfileSaved> {
    return this.http.put<ChildProfileSaved>('/api/profile', profile);
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
    changes: StoryChanges,
  ): Observable<Story> {
    return this.http.patch<Story>(`/api/stories/${id}`, changes);
  }

  deleteStory(id: number): Observable<void> {
    return this.http.delete<void>(`/api/stories/${id}`);
  }

  /** Starts the adventure agent; the run page then streams its steps. */
  planAdventure(request: AdventureRequest): Observable<AgentRun> {
    return this.http.post<AgentRun>('/api/adventures', request);
  }

  getAdventure(id: number): Observable<Adventure> {
    return this.http.get<Adventure>(`/api/adventures/${id}`);
  }

  /** Starts the agent on the adventure's next chapter. */
  writeNextChapter(adventureId: number): Observable<AgentRun> {
    return this.http.post<AgentRun>(`/api/adventures/${adventureId}/next`, {});
  }

  getRun(id: number): Observable<AgentRun> {
    return this.http.get<AgentRun>(`/api/agent-runs/${id}`);
  }
}
