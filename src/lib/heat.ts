/**
 * Heat-map cell colours. A cell is the series colour mixed into the page
 * surface as an opaque colour, so the ink can be chosen against it. A
 * translucent fill (rgba) takes its contrast from whatever sits behind it,
 * which is how white text landed on a pale blue.
 *
 * Two bands, because no single ink clears 4.5:1 across the whole ramp:
 * below 0.6 the cell is a light tint and carries the theme's text colour;
 * from 0.6 up it is a deep blue and carries white. scripts or tests that
 * change the base colour must re-measure both bands in both themes.
 */
export function heat(intensity: number, base = '#1d4ed8'): { background: string; color: string } {
  const t = Math.max(0, Math.min(1, intensity));
  if (t < 0.6) {
    const pct = Math.round(10 + (t / 0.6) * 45); // 10% to 55% of the base
    return {
      background: `color-mix(in srgb, ${base} ${pct}%, var(--color-bg-white))`,
      color: 'var(--color-text)',
    };
  }
  const pct = Math.round(88 + ((t - 0.6) / 0.4) * 12); // 88% to 100% of the base, over near-black
  return {
    background: `color-mix(in srgb, ${base} ${pct}%, #0b1230)`,
    color: '#fff',
  };
}
