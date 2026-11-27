import { Component, input, output, signal } from '@angular/core';

/** A Delete button that asks once more on the page before it emits. */
@Component({
  selector: 'app-confirm-delete',
  template: `
    @if (asking()) {
      <span class="ask">
        <button type="button" class="danger" (click)="confirm()">Confirm delete</button>
        <button type="button" class="plain" (click)="asking.set(false)">Cancel</button>
      </span>
    } @else {
      <button type="button" class="plain" [disabled]="disabled()" (click)="asking.set(true)">{{ label() }}</button>
    }
  `,
  styles: '.ask { display: inline-flex; gap: 8px; }',
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
