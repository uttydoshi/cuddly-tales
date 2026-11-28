import { AgentStep, Night } from '../../models';
import { duration, nightStatus, upsert } from './agent-run';

function step(id: number, position: number, extra: Partial<AgentStep> = {}): AgentStep {
  return {
    id,
    position,
    tool: 'write_chapter',
    label: 'Write night 1',
    result: null,
    ok: null,
    detail: null,
    started_at: '2026-11-28T10:00:00Z',
    finished_at: null,
    ...extra,
  };
}

describe('agent run helpers', () => {
  it('replaces a step that finishes, keeping the order', () => {
    const started = [step(1, 0, { ok: true }), step(2, 1)];
    const finished = upsert(started, step(2, 1, { ok: true, result: '412 words' }));
    expect(finished.map((s) => [s.id, s.ok])).toEqual([
      [1, true],
      [2, true],
    ]);
    expect(upsert(finished, step(3, 2)).map((s) => s.id)).toEqual([1, 2, 3]);
  });

  it('times steps, live while running, and hides instant ones', () => {
    const now = Date.parse('2026-11-28T10:00:04.2Z');
    expect(duration(step(1, 0), now)).toBe('4.2s');
    expect(duration(step(1, 0, { finished_at: '2026-11-28T10:00:15Z' }), now)).toBe('15s');
    expect(duration(step(1, 0, { finished_at: '2026-11-28T10:00:00.1Z' }), now)).toBe('');
  });

  it('labels each night of the plan', () => {
    const night = (extra: Partial<Night>): Night => ({
      night: 1,
      story_id: 1,
      title: 'T',
      status: 'written',
      safety_status: 'passed',
      plot_cards: [],
      ...extra,
    });
    expect(nightStatus(night({ status: 'planned', safety_status: null })).label).toBe('Planned');
    expect(nightStatus(night({ safety_status: 'needs_review' })).label).toBe('Read first');
    expect(nightStatus(night({ status: 'read' })).label).toBe('Read');
    expect(nightStatus(night({})).label).toBe('Ready to read');
  });
});
