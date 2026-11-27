import { Component, input, output, signal } from '@angular/core';

/** A Delete button that asks once more on the page before it emits. */
@Component({
  selector: 'app-confirm-delete',
  template: `
    @if (asking()) {
      <span class="ask">
        <button type="button" class="btn danger" (click)="confirm()">Yes, delete</button>
        <button type="button" class="btn quiet" (click)="asking.set(false)">Keep it</button>
      </span>
    } @else {
      <button type="button" class="btn quiet" [disabled]="disabled()" (click)="asking.set(true)">{{ label() }}</button>
    }
  `,
  styles: '.ask { display: inline-flex; flex-wrap: wrap; gap: 0.5rem; }',
})
export class ConfirmDelete {
  readonly label = input('Delete');
  readonly disabled = input(false);
  readonly confirmed = output<void>();
  readonly asking = signal(false);

  confirm(): void {
    this.asking.set(false);
    this.confirmed.emit();
  }
}
