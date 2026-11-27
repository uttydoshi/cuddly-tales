export type CharacterType = 'family' | 'original' | 'folklore' | 'latte_monster' | 'custom';
export type StoryStatus = 'idea' | 'planned' | 'written' | 'read';

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

export interface CharacterRef {
  id: number;
  name: string;
}

export interface StorySummary {
  id: number;
  title: string;
  status: StoryStatus;
  word_count: number | null;
  reading_minutes: number | null;
  created_at: string;
  characters: CharacterRef[];
}

export interface Story extends StorySummary {
  text: string | null;
  read_at: string | null;
}

export type StreamEvent =
  | { type: 'word'; text: string }
  | { type: 'done'; id: number; title: string | null }
  | { type: 'error'; message: string };
