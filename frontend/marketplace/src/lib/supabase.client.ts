import { createBrowserClient } from '@supabase/ssr'
import type { SupabaseClient } from '@supabase/supabase-js'

let browserClient: SupabaseClient | null = null

export function getSupabaseBrowserClient() {
  if (browserClient) return browserClient

  const url = import.meta.env.VITE_SUPABASE_URL
  const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY

  if (!url || !anonKey) {
    throw new Error('Missing VITE_SUPABASE_URL or VITE_SUPABASE_ANON_KEY')
  }

  browserClient = createBrowserClient(url, anonKey)
  return browserClient
}

export type Product = {
  id: string
  title: string
  description: string | null
  price: number
  image_url: string | null
  seller_name: string | null
  stock: number
}

export type CartLine = {
  id: string
  quantity: number
  product: Product
  subtotal: number
}

export type CartPayload = {
  items: CartLine[]
  itemCount: number
  subtotal: number
}
