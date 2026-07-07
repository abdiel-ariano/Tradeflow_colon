import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export const currencyUsd = new Intl.NumberFormat('es-MX', {
  style: 'currency',
  currency: 'USD',
  minimumFractionDigits: 2,
})

export function formatUsd(value: number) {
  return currencyUsd.format(value)
}

export const SHIPPING_FREE_THRESHOLD = 500
export const SHIPPING_COST = 99
export const TAX_RATE = 0.16

export function calcOrderTotals(subtotal: number) {
  const shipping = subtotal > SHIPPING_FREE_THRESHOLD || subtotal === 0 ? 0 : SHIPPING_COST
  const taxes = subtotal * TAX_RATE
  const total = subtotal + shipping + taxes
  return { subtotal, shipping, taxes, total }
}
