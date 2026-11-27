import { Component, inject } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';

import { Footer } from './shared/footer';
import { ShellService } from './shared/shell.service';

@Component({
  imports: [RouterOutlet, RouterLink, RouterLinkActive, Footer],
  selector: 'app-root',
  styleUrl: './app.css',
  templateUrl: './app.html',
})
export class App {
  protected readonly shell = inject(ShellService);
}
