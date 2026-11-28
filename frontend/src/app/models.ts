export type CharacterType = 'family' | 'original' | 'folklore' | 'latte_monster' | 'custom';
export type StoryStatus = 'idea' | 'planned' | 'written' | 'read';
/** The safety and age check. null: not written yet, or written before the check existed. */
export type SafetyStatus = 'passed' | 'rewritten' | 'needs_review' | 'approved';

export interface ChildProfile {
  id: number;
  name: string;
  age: number;
  favourite_things: string[];
}

/** What saving the profile returns: how many stories now say the new name. */
export interface ChildProfileSaved extends ChildProfile {
  stories_renamed: number;
}

/** A parent's changes to a story. Only the fields sent are changed. */
export interface StoryChanges {
  title?: string;
  text?: string;
  read?: boolean;
  approve?: boolean;
  favourite?: boolean;
}

export interface Character {
  id: number;
  name: string;
  type: CharacterType;
  description: string;
  traits: string[];
  rules: string[];
  image_url: string | null;
}

/** What a parent can set when adding or editing a character. */
export type CharacterInput = Pick<Character, 'name' | 'type' | 'description' | 'traits' | 'rules'>;

export interface CharacterRef {
  id: number;
  name: string;
  type: CharacterType;
}

export interface StorySummary {
  id: number;
  title: string;
  status: StoryStatus;
  word_count: number | null;
  reading_minutes: number | null;
  created_at: string;
  /** Bedtime stories end calm and sleepy and open in night mode; others are for any time. */
  bedtime: boolean;
  /** A parent's heart: the story shows under Favourites. */
  favourite: boolean;
  characters: CharacterRef[];
  safety_status: SafetyStatus | null;
  /** Set when the story is one chapter of an adventure. */
  adventure: AdventureRef | null;
}

export interface AdventureRef {
  id: number;
  title: string;
  chapter: number;
  chapter_count: number;
}

export interface SafetyAttempt {
  passed: boolean;
  word_count: number;
  scariness: number | null;
  problems: string[];
}

export interface Story extends StorySummary {
  text: string | null;
  read_at: string | null;
  /** Every version the check looked at, first to last. */
  safety: { attempts: SafetyAttempt[] } | null;
  /** The plot beat by beat, for adventure chapters. */
  plot_cards: string[];
}

export type StreamEvent =
  | { type: 'word'; text: string }
  | { type: 'checking' }
  | { type: 'rewriting'; problems: string[] }
  | { type: 'done'; id: number; title: string | null }
  | { type: 'error'; message: string };

/** One chapter of an adventure, as planned (and later written). */
export interface Chapter {
  chapter: number;
  story_id: number;
  title: string;
  status: StoryStatus;
  safety_status: SafetyStatus | null;
  plot_cards: string[];
}

export interface Adventure {
  id: number;
  title: string;
  premise: string;
  chapter_count: number;
  bedtime: boolean;
  status: 'in_progress' | 'finished';
  created_at: string;
  chapters: Chapter[];
}

export interface AdventureRequest {
  chapter_count: number;
  bedtime: boolean;
  character_ids: number[];
  theme: string | null;
}

/** One thing the agent did: a tool call, or what it said between tools (tool "message"). */
export interface AgentStep {
  id: number;
  position: number;
  tool: string;
  label: string;
  result: string | null;
  /** null while the step is still running. */
  ok: boolean | null;
  detail: { input: unknown; output: unknown } | null;
  started_at: string;
  finished_at: string | null;
}

export type AgentRunStatus = 'pending' | 'running' | 'finished' | 'failed' | 'stopped';

export interface AgentRun {
  id: number;
  kind: 'plan' | 'next_chapter';
  goal: string;
  status: AgentRunStatus;
  trigger: string;
  error: string | null;
  created_at: string;
  finished_at: string | null;
  adventure: Adventure | null;
  steps: AgentStep[];
}

export type AgentEvent = { type: 'step'; step: AgentStep } | { type: 'done'; run: AgentRun } | { type: 'lost' };
