import { SafetyStatus } from '../models';

/** The short line under a story saying how the safety and age check went. Empty when there's
 *  nothing reassuring to say: not checked yet, or flagged (that gets its own notice). */
export function safetyNote(status: SafetyStatus | null | undefined, age?: number): string {
  const forAge = age ? ` for age ${age}` : '';
  switch (status) {
    case 'passed':
      return `Checked: gentle${forAge}`;
    case 'rewritten':
      return `Checked: rewritten once to be just right${forAge}`;
    case 'approved':
      return 'Checked: you read it and said it’s fine';
    default:
      return '';
  }
}
