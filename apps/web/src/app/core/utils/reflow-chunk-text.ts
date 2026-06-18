const SPECIAL_SPACE = /[\u00a0\u202f]/g;
const TRAILING_HYPHEN =
  /[-\u00ad\u2010\u2011\u2012\u2013\u2014\u2015\u2212]+$/;

/** Reflow PDF line breaks and hyphenation for readable display. */
export function reflowChunkText(text: string): string {
  const normalized = text.replace(SPECIAL_SPACE, ' ');
  return normalized
    .split(/\n\s*\n/)
    .map(reflowParagraph)
    .filter(Boolean)
    .join('\n\n');
}

function reflowParagraph(paragraph: string): string {
  const lines = paragraph
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean);
  if (lines.length === 0) {
    return '';
  }

  let result = lines[0]!;
  for (let i = 1; i < lines.length; i++) {
    const line = lines[i]!;
    if (TRAILING_HYPHEN.test(result)) {
      result = result.replace(TRAILING_HYPHEN, '') + line;
    } else {
      result += ` ${line}`;
    }
  }
  return result.replace(/ {2,}/g, ' ').trim();
}
