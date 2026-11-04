export function clock(iso: string): string {
  return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export function lb(n: number): string {
  return `${Math.round(n).toLocaleString("en-US")} lb`;
}

export function minutes(n: number): string {
  return Number.isInteger(n) ? `${n} min` : `${n.toFixed(1)} min`;
}
