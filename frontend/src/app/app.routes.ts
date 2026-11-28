import { Routes } from '@angular/router';

export const routes: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'new' },
  {
    path: 'new',
    title: 'New story · Cuddly Tales',
    loadComponent: () => import('./pages/new-story/new-story').then((m) => m.NewStory),
  },
  {
    path: 'stories',
    title: 'Stories · Cuddly Tales',
    loadComponent: () => import('./pages/story-list/story-list').then((m) => m.StoryList),
  },
  {
    path: 'stories/:id',
    title: 'Story · Cuddly Tales',
    loadComponent: () => import('./pages/story-detail/story-detail').then((m) => m.StoryDetail),
  },
  {
    path: 'adventures/runs/:id',
    title: 'Adventure planner · Cuddly Tales',
    loadComponent: () => import('./pages/agent-run/agent-run').then((m) => m.AgentRunPage),
  },
  {
    path: 'characters',
    title: 'Characters · Cuddly Tales',
    loadComponent: () => import('./pages/characters/characters').then((m) => m.Characters),
  },
  {
    path: 'characters/new',
    title: 'Add a character · Cuddly Tales',
    loadComponent: () => import('./pages/character-form/character-form').then((m) => m.CharacterForm),
  },
  {
    path: 'characters/:id/edit',
    title: 'Edit character · Cuddly Tales',
    loadComponent: () => import('./pages/character-form/character-form').then((m) => m.CharacterForm),
  },
  {
    path: 'profile',
    title: 'Your child · Cuddly Tales',
    loadComponent: () => import('./pages/profile/profile').then((m) => m.Profile),
  },
  { path: '**', redirectTo: 'new' },
];
