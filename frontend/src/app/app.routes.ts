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
  { path: '**', redirectTo: 'new' },
];
