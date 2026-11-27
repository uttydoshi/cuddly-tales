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
  characters: CharacterRef[];
  safety_status: SafetyStatus | null;
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
}

export type StreamEvent =
  | { type: 'word'; text: string }
  | { type: 'checking' }
  | { type: 'rewriting'; problems: string[] }
  | { type: 'done'; id: number; title: string | null }
  | { type: 'error'; message: string };
