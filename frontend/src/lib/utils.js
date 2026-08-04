import { clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

/** Merge conditional class lists, de-duplicating conflicting Tailwind classes (shadcn's cn). */
export function cn(...inputs) {
  return twMerge(clsx(inputs))
}

/** Posture (0-100, HIGHER is better) → semantic token color. Green when strong, red when weak. */
export function postureColor(v) {
  if (v == null) return 'var(--ghost)'
  if (v >= 85) return 'var(--risk-low)'        // A — strong (green)
  if (v >= 70) return 'var(--risk-moderate)'   // B
  if (v >= 50) return 'var(--risk-high)'       // C
  return 'var(--risk-critical)'                // D/F — weak (red)
}

/** Grade letter → the same posture color, keyed off the letter. */
export function gradeColor(grade) {
  return { A: 'var(--risk-low)', B: 'var(--risk-moderate)', C: 'var(--risk-high)',
    D: 'var(--risk-critical)', F: 'var(--risk-critical)' }[grade] || 'var(--ghost)'
}

/** Confidence (0-1) → token color: strong / caution / ghost.
 *
 * Thresholds MIRROR `confidence.bands` in scoring.yaml (High >=0.90, Medium >=0.70, else Low).
 * They used to be 0.7 / 0.4, which disagreed with the band the backend computes: a vendor at 0.75
 * was labelled "Medium" and painted green, and one at 0.50 was labelled "Low" and painted amber.
 * Harmless while the colour and the word sat apart on the card; a direct contradiction now that
 * the band name is rendered inside a swatch tinted by this function.
 */
export function confColor(c) {
  return c >= 0.9 ? 'var(--risk-low)' : c >= 0.7 ? 'var(--risk-moderate)' : 'var(--ghost)'
}
