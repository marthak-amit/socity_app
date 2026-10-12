/** Format whole rupees with Indian digit grouping: 1500 → ₹1,500, 1234567 → ₹12,34,567. */
export function formatINR(amount: number): string {
  const negative = amount < 0;
  const digits = Math.abs(Math.round(amount)).toString();
  let out: string;
  if (digits.length <= 3) {
    out = digits;
  } else {
    const last3 = digits.slice(-3);
    const rest = digits.slice(0, -3).replace(/\B(?=(\d{2})+(?!\d))/g, ',');
    out = `${rest},${last3}`;
  }
  return `${negative ? '-' : ''}₹${out}`;
}

export function priceLabel(price: number): string {
  return price === 0 ? 'Free' : formatINR(price);
}
