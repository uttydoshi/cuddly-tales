import { isEvening } from './new-story';

describe('isEvening', () => {
  it('starts on Bedtime from 6pm to 6am, and Anytime during the day', () => {
    const at = (hour: number) => new Date(2026, 10, 27, hour, 30);
    expect(isEvening(at(5))).toBe(true);
    expect(isEvening(at(6))).toBe(false);
    expect(isEvening(at(12))).toBe(false);
    expect(isEvening(at(17))).toBe(false);
    expect(isEvening(at(18))).toBe(true);
    expect(isEvening(at(23))).toBe(true);
  });
});
