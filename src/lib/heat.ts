/**
 * Heat-map cell colours. A cell is a mix of the series colour and the page
 * surface, written as an opaque colour so the ink can be chosen against it.
 * Translucent fills (rgba) took their contrast from whatever sat behind
 * them, which is how white text landed on a pale blue.
 *
 * Dark ink up to 85% intensity, and the theme's high-contrast ink above it
 * (white in the light theme, where the cell is then dark enough to carry it).
 */
export function heat(intensity: number, base = '#1d4ed8'): { background: string; color: string } {
  const t = Math.max(0, Math.min(1, intensity));
  const pct = Math.round(t * 100);
  return {
    background: `color-mix(in srgb, ${base} ${pct}%, var(--color-bg-white))`,
    color: t >= 0.85 ? 'var(--cell-hi-ink)' : 'var(--color-text)',
  };
}
