import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export const MONTHS_EN = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
];

const MONTH_ES_TO_EN: Record<string, string> = {
  Ene: 'Jan',
  Abr: 'Apr',
  Ago: 'Aug',
  Dic: 'Dec',
};

/** Normalize API month abbreviations to English. */
export function monthLabelEn(label: string | undefined): string {
  if (!label) return '';
  return MONTH_ES_TO_EN[label] ?? label;
}

export const currencyUsd = new Intl.NumberFormat('es-CO', {
  style: 'currency',
  currency: 'USD',
  maximumFractionDigits: 0,
});

export function formatUsdK(value: number): string {
  if (value >= 1000) return `$${(value / 1000).toFixed(0)}k`;
  return currencyUsd.format(value);
}

export function linearRegressionForecast(values: number[], forecastCount: number): number[] {
  const n = values.length;
  if (n === 0) return Array(forecastCount).fill(0);
  if (n === 1) return Array(forecastCount).fill(values[0]);
  const xs = values.map((_, i) => i);
  const sumX = xs.reduce((a, b) => a + b, 0);
  const sumY = values.reduce((a, b) => a + b, 0);
  const sumXY = xs.reduce((acc, x, i) => acc + x * values[i], 0);
  const sumX2 = xs.reduce((acc, x) => acc + x * x, 0);
  const denom = n * sumX2 - sumX * sumX;
  const slope = denom === 0 ? 0 : (n * sumXY - sumX * sumY) / denom;
  const intercept = (sumY - slope * sumX) / n;
  return Array.from({ length: forecastCount }, (_, i) =>
    Math.max(0, intercept + slope * (n + i)),
  );
}
