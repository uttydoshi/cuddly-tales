import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { StreamEvent } from '../models';

/** Wraps the browser's EventSource for GET /api/stories/{id}/stream. */
@Injectable({ providedIn: 'root' })
export class StoryStreamService {
  stream(storyId: number): Observable<StreamEvent> {
    return new Observable<StreamEvent>((subscriber) => {
      const source = new EventSource(`/api/stories/${storyId}/stream`);
      const finish = () => {
        source.close(); // stop EventSource from reconnecting and starting a second story
        subscriber.complete();
      };

      source.addEventListener('word', (event) => {
        const data = JSON.parse((event as MessageEvent).data);
        subscriber.next({ type: 'word', text: data.text });
      });

      source.addEventListener('done', (event) => {
        const data = JSON.parse((event as MessageEvent).data);
        subscriber.next({ type: 'done', id: data.id, title: data.title });
        finish();
      });

      // Fires both for the server's own "error" event (which has data)
      // and for a dropped connection (which does not).
      source.addEventListener('error', (event) => {
        const raw = (event as MessageEvent).data;
        const message = raw ? JSON.parse(raw).message : 'Lost the connection while the story was being written.';
        subscriber.next({ type: 'error', message });
        finish();
      });

      return () => source.close();
    });
  }
}
