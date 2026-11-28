import { SafetyStatus } from '../models';

/** The short line under a story saying how the AI's safety and age check went (the parent's own
 *  sign-off is separate: Verified). Empty when not checked yet, or flagged (that gets its own notice). */
export function safetyNote(status: SafetyStatus | null | undefined, age?: number): string {
  const forAge = age ? ` for age ${age}` : '';
  switch (status) {
    case 'passed':
      return `Checked: gentle${forAge}`;
    case 'rewritten':
      return `Checked: rewritten once to be just right${forAge}`;
    case 'approved':
      return 'Flagged by the check, then verified by you';
    default:
      return '';
  }
}
