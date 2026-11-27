import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { Character, ChildProfile, Story, StorySummary } from '../models';

@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly http = inject(HttpClient);

  getProfile(): Observable<ChildProfile> {
    return this.http.get<ChildProfile>('/api/profile');
  }

  listCharacters(): Observable<Character[]> {
    return this.http.get<Character[]>('/api/characters');
  }

  createStory(characterIds: number[]): Observable<Story> {
    return this.http.post<Story>('/api/stories', { character_ids: characterIds });
  }

  listStories(): Observable<StorySummary[]> {
    return this.http.get<StorySummary[]>('/api/stories');
  }

  getStory(id: number): Observable<Story> {
    return this.http.get<Story>(`/api/stories/${id}`);
  }
}
