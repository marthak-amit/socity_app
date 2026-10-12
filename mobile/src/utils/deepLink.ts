/** Extract an invite code from a deep link, web link or a bare code typed/scanned by the user. */
export function parseInviteCode(input: string): string | null {
  const text = input.trim();
  if (!text) return null;
  const query = text.match(/[?&]code=([A-Za-z0-9]+)/);
  if (query) return query[1].toUpperCase();
  const path = text.match(/\/join\/([A-Za-z0-9]+)/);
  if (path) return path[1].toUpperCase();
  if (/^[A-Za-z0-9]{4,12}$/.test(text)) return text.toUpperCase();
  return null;
}
