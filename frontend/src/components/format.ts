const numberFormatter = new Intl.NumberFormat("en-US");
const compactFormatter = new Intl.NumberFormat("en-US", {
  notation: "compact",
  maximumFractionDigits: 1,
});
const dateFormatter = new Intl.DateTimeFormat("en-US", {
  month: "short",
  day: "numeric",
  hour: "numeric",
  minute: "2-digit",
});

export function formatCount(value: number, compact = false): string {
  return (compact ? compactFormatter : numberFormatter).format(value);
}

export function formatPercent(value: number | null, digits = 1): string {
  return value === null ? "—" : `${(value * 100).toFixed(digits)}%`;
}

export function formatQuality(value: number | null): string {
  return value === null ? "—" : value.toFixed(3);
}

export function formatDate(value: string | null): string {
  if (!value) return "Not finished";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : dateFormatter.format(date);
}

export function formatBytes(value: number | null): string {
  if (value === null) return "Calculating";
  if (value < 1024) return `${value} B`;
  if (value < 1024 ** 2) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / 1024 ** 2).toFixed(1)} MB`;
}

export function formatMoney(value: number | null): string {
  if (value === null) return "Not available";
  if (value === 0) return "$0.00";
  if (value < 0.01) return `$${value.toFixed(4)}`;
  return `$${value.toFixed(2)}`;
}

export function formatExportFormat(value: string): string {
  const labels: Record<string, string> = {
    canonical_jsonl: "Canonical JSONL",
    openai_chat_jsonl: "OpenAI chat JSONL",
    alpaca_jsonl: "Alpaca JSONL",
    parquet: "Parquet splits",
  };
  return labels[value] ?? value;
}
