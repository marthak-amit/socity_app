/** Fallback builder for a UPI deep link (the API normally returns `upi_uri` already). */
export function buildUpiUri(p: { pa: string; pn: string; am: number; tn: string }): string {
  const q = [
    ['pa', p.pa],
    ['pn', p.pn],
    ['am', p.am.toFixed(2)],
    ['cu', 'INR'],
    ['tn', p.tn],
  ]
    .map(([k, v]) => `${k}=${encodeURIComponent(v)}`)
    .join('&');
  return `upi://pay?${q}`;
}
