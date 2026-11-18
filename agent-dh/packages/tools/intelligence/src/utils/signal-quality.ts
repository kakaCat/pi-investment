export const SIGNAL_SOURCES = [
  'strategy_execute',
  'opportunity_scan',
  'mainline_stocks',
  'watch_rule',
  'manual',
] as const;

export type SignalSource = typeof SIGNAL_SOURCES[number];
export type SignalQualityAction = 'downgrade' | 'maintain' | 'reduce_half' | 'review' | 'insufficient';

export interface SignalQualityInput {
  matureCount: number;
  hitRate5d: number | null;
  avgReturn5d: number | null;
  minSamples?: number;
}

export function evaluateSignalSourceQuality(input: SignalQualityInput): SignalQualityAction {
  const minSamples = input.minSamples ?? 7;
  if (input.matureCount < minSamples || input.hitRate5d === null || input.avgReturn5d === null) {
    return 'insufficient';
  }
  if (input.hitRate5d < 0.25 && input.avgReturn5d < 0) return 'downgrade';
  if (input.hitRate5d >= 0.4 && input.avgReturn5d > 0) return 'maintain';
  if (input.hitRate5d >= 0.4 && input.avgReturn5d <= 0) return 'reduce_half';
  return 'review';
}
