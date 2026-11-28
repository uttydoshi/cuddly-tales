import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { AgentEvent } from '../models';

/** Wraps EventSource for GET /api/agent-runs/{id}/stream: each step as it starts and finishes, then the run. */
@Injectable({ providedIn: 'root' })
export class AgentStreamService {
  stream(runId: number): Observable<AgentEvent> {
    return new Observable<AgentEvent>((subscriber) => {
      const source = new EventSource(`/api/agent-runs/${runId}/stream`);
      const finish = () => {
        source.close(); // never reconnect: a run can only be streamed once
        subscriber.complete();
      };
      source.addEventListener('step', (event) => {
        subscriber.next({ type: 'step', step: JSON.parse((event as MessageEvent).data) });
      });
      source.addEventListener('done', (event) => {
        subscriber.next({ type: 'done', run: JSON.parse((event as MessageEvent).data) });
        finish();
      });
      source.addEventListener('error', () => {
        subscriber.next({ type: 'lost' });
        finish();
      });
      return () => source.close();
    });
  }
}
