import { Component, DestroyRef, computed, effect, inject, input, signal, untracked } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Subscription } from 'rxjs';

import { AgentRun, AgentStep, Night } from '../../models';
import { AgentStreamService } from '../../services/agent-stream.service';
import { ApiService } from '../../services/api.service';

const POLL_MS = 3000;

/** Seconds a step took (or has taken so far), like "4.2s"; empty for quick steps. */
export function duration(step: AgentStep, now: number): string {
  const start = Date.parse(step.started_at);
  const end = step.finished_at ? Date.parse(step.finished_at) : now;
  const seconds = Math.max(0, (end - start) / 1000);
  if (step.finished_at && seconds < 0.5) {
    return '';
  }
  return seconds < 10 ? `${seconds.toFixed(1)}s` : `${Math.round(seconds)}s`;
}

/** A step arrives twice (started, then finished): replace it in place, or add it in order. */
export function upsert(steps: AgentStep[], step: AgentStep): AgentStep[] {
  const others = steps.filter((s) => s.id !== step.id);
  return [...others, step].sort((a, b) => a.position - b.position);
}

/** How a night reads in the plan: "Ready to read", "Read first", "Read" or "Planned". */
export function nightStatus(night: Night): { label: string; tone: 'ok' | 'warn' | 'quiet' | '' } {
  if (night.status === 'planned') {
    return { label: 'Planned', tone: 'quiet' };
  }
  if (night.safety_status === 'needs_review') {
    return { label: 'Read first', tone: 'warn' };
  }
  return night.status === 'read' ? { label: 'Read', tone: 'ok' } : { label: 'Ready to read', tone: '' };
}

/**
 * The adventure agent at work: each step as it happens (what it's doing, the tool it called,
 * what came back), then the plan it made. Opening a run that hasn't started starts it; opening
 * one that has shows what it did.
 */
@Component({
  selector: 'app-agent-run',
  imports: [RouterLink],
  templateUrl: './agent-run.html',
  styleUrl: './agent-run.css',
})
export class AgentRunPage {
  private readonly api = inject(ApiService);
  private readonly streams = inject(AgentStreamService);

  /** Bound from the :id route parameter. */
  readonly id = input.required<string>();

  readonly run = signal<AgentRun | null>(null);
  readonly steps = signal<AgentStep[]>([]);
  readonly notFound = signal(false);
  readonly now = signal(Date.now());
  readonly actionError = signal('');
  readonly starting = signal(false);

  readonly working = computed(() => ['pending', 'running'].includes(this.run()?.status ?? ''));
  readonly toolCalls = computed(() => this.steps().filter((s) => s.tool !== 'message').length);
  readonly totalTime = computed(() => {
    const run = this.run();
    if (!run?.finished_at || !this.steps().length) {
      return '';
    }
    const seconds = (Date.parse(run.finished_at) - Date.parse(this.steps()[0].started_at)) / 1000;
    return `${Math.round(seconds)} seconds`;
  });
  /** The night this run saved, to read straight away. */
  readonly savedNight = computed(() => {
    const saved = this.steps().find((s) => s.tool === 'save_story' && s.ok);
    const storyId = (saved?.detail?.output as { story_id?: number } | undefined)?.story_id;
    return this.run()?.adventure?.chapters.find((c) => c.story_id === storyId) ?? null;
  });
  readonly nextNight = computed(() => this.run()?.adventure?.chapters.find((c) => c.status === 'planned') ?? null);

  readonly duration = duration;
  readonly nightStatus = nightStatus;

  private stream?: Subscription;
  private poll?: ReturnType<typeof setInterval>;
  private clock?: ReturnType<typeof setInterval>;

  constructor() {
    inject(DestroyRef).onDestroy(() => this.stop());

    effect((onCleanup) => {
      const id = Number(this.id());
      untracked(() => this.stop());
      const sub = this.api.getRun(id).subscribe({
        next: (run) => {
          this.show(run);
          if (run.status === 'pending') {
            this.watch(run.id);
          } else if (run.status === 'running') {
            this.pollUntilDone(run.id); // started elsewhere (another tab, or before a reload)
          }
        },
        error: () => this.notFound.set(true),
      });
      onCleanup(() => sub.unsubscribe());
    });
  }

  /** "Write the next night now": a new run, on its own page. */
  writeNext(adventureId: number): void {
    this.starting.set(true);
    this.actionError.set('');
    this.api.writeNextNight(adventureId).subscribe({
      next: (run) => {
        this.starting.set(false);
        this.run.set(null);
        this.steps.set([]);
        history.pushState(null, '', `/adventures/runs/${run.id}`);
        this.show(run);
        this.watch(run.id);
      },
      error: (error) => {
        this.starting.set(false);
        this.actionError.set(error.error?.detail ?? 'Could not start the next night. Please try again.');
      },
    });
  }

  details(step: AgentStep): string {
    return JSON.stringify(step.detail, null, 2);
  }

  private show(run: AgentRun): void {
    this.run.set(run);
    this.steps.set(run.steps);
  }

  private watch(runId: number): void {
    this.tick();
    this.stream = this.streams.stream(runId).subscribe((event) => {
      if (event.type === 'step') {
        this.steps.update((steps) => upsert(steps, event.step));
        this.run.update((run) => (run && run.status === 'pending' ? { ...run, status: 'running' } : run));
      } else if (event.type === 'done') {
        this.show(event.run);
        this.stopClock();
      } else {
        // The connection dropped: the server stops the run; show what it saved.
        this.api.getRun(runId).subscribe((run) => this.show(run));
        this.stopClock();
      }
    });
  }

  private pollUntilDone(runId: number): void {
    this.tick();
    this.poll = setInterval(() => {
      this.api.getRun(runId).subscribe((run) => {
        this.show(run);
        if (!['pending', 'running'].includes(run.status)) {
          clearInterval(this.poll);
          this.stopClock();
        }
      });
    }, POLL_MS);
  }

  private tick(): void {
    this.clock = setInterval(() => this.now.set(Date.now()), 250);
  }

  private stopClock(): void {
    clearInterval(this.clock);
  }

  private stop(): void {
    this.stream?.unsubscribe();
    clearInterval(this.poll);
    this.stopClock();
  }
}
