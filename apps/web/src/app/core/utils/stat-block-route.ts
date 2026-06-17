export function encodeStatBlockName(name: string): string {
  return encodeURIComponent(name);
}

export function decodeStatBlockName(name: string): string {
  return decodeURIComponent(name);
}
