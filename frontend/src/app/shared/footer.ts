import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';

/** The site footer: a dark band across the full width, in the style of ukdoshi.com's. */
@Component({
  selector: 'app-footer',
  imports: [RouterLink],
  template: `
    <footer class="site-footer">
      <div class="inner">
        <div class="top">
          <p class="tagline">Gentle stories,<br />sweet dreams.</p>
          <nav class="links" aria-label="Footer">
            <div>
              <h2>Explore</h2>
              <ul>
                <li><a routerLink="/new">Write a story</a></li>
                <li><a routerLink="/stories">Your stories</a></li>
                <li><a routerLink="/characters">Characters</a></li>
                <li><a routerLink="/profile">Your child</a></li>
              </ul>
            </div>
            <div>
              <h2>Behind it</h2>
              <ul>
                <li><a href="https://github.com/uttydoshi/cuddly-tales#readme" target="_blank" rel="noopener">How it's built</a></li>
                <li><a href="https://ukdoshi.com" target="_blank" rel="noopener">ukdoshi.com</a></li>
              </ul>
            </div>
          </nav>
        </div>
        <div class="bottom">
          <a class="brand" routerLink="/new" aria-label="Cuddly Tales home">
            <svg viewBox="0 0 40 40" aria-hidden="true">
              <path d="M20 3 L35 11.5 V28.5 L20 37 L5 28.5 V11.5 Z" stroke-width="2.5" />
              <path d="M24.5 13.5 a7.5 7.5 0 1 0 2.8 11.6 a6 6 0 0 1 -2.8 -11.6 Z" stroke-width="2.2" />
            </svg>
            Cuddly Tales
          </a>
          <p class="by">A side project by <a href="https://ukdoshi.com" target="_blank" rel="noopener">ukdoshi.com</a></p>
        </div>
      </div>
    </footer>
  `,
  styles: `
    :host {
      display: block;
    }

    .site-footer {
      margin-top: 2.5rem;
      background: var(--dark);
      color: rgb(255 255 255 / 0.6);
      font-size: 0.9rem;
    }

    .inner {
      box-sizing: border-box;
      max-width: var(--content-width);
      margin: 0 auto;
      padding: 2rem max(1.25rem, env(safe-area-inset-right, 0px)) 1.25rem max(1.25rem, env(safe-area-inset-left, 0px));
    }

    .top {
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      gap: 2rem 4rem;
    }

    .tagline {
      margin: 0;
      font-family: var(--font-heading);
      font-size: clamp(1.5rem, 5vw, 2rem);
      font-weight: 500;
      line-height: 1.15;
      letter-spacing: -0.01em;
      color: #ffffff;
    }

    .links {
      display: flex;
      flex-wrap: wrap;
      gap: 1.75rem 4rem;
    }

    h2 {
      margin: 0 0 0.6rem;
      font-family: var(--font-body);
      font-size: 0.85rem;
      font-weight: 400;
      letter-spacing: 0;
      color: rgb(255 255 255 / 0.55);
    }

    ul {
      margin: 0;
      padding: 0;
      list-style: none;
    }

    li + li {
      margin-top: 0.15rem;
    }

    @media (min-width: 768px) {
      .inner {
        padding-left: 1.5rem;
        padding-right: 1.5rem;
      }
    }

    a {
      display: inline-flex;
      align-items: center;
      min-height: 2rem;
      color: #ffffff;
      text-decoration: none;
    }

    a:hover {
      text-decoration: underline;
    }

    a:focus-visible {
      outline: 2px solid #ffffff;
      outline-offset: 3px;
    }

    .bottom {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 0.75rem 1rem;
      margin-top: 1.5rem;
      padding-top: 1rem;
      border-top: 1px solid rgb(255 255 255 / 0.12);
    }

    .brand {
      gap: 0.75rem;
      font-size: 0.95rem;
      font-weight: 600;
      letter-spacing: 0.2em;
      text-transform: uppercase;
    }

    .brand:hover {
      text-decoration: none;
    }

    .brand svg {
      width: 2.5rem;
      height: 2.5rem;
      fill: none;
      stroke: #ffffff;
      stroke-linejoin: round;
    }

    .by {
      margin: 0;
      font-size: 0.85rem;
    }

    .by a {
      min-height: 0;
      text-decoration: underline;
      text-underline-offset: 0.2em;
    }
  `,
})
export class Footer {}
