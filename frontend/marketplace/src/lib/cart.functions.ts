import { createServerFn } from '@tanstack/react-start'
import { z } from 'zod'
import { requireSupabaseAuth } from './auth.middleware'
import { createSupabaseServerClient } from './supabase.server'
import type { CartLine, CartPayload, Product } from './supabase.client'

const addToCartSchema = z.object({
  productId: z.string().uuid(),
  quantity: z.coerce.number().int().positive().default(1),
})

const updateCartItemSchema = z.object({
  itemId: z.string().uuid(),
  quantity: z.coerce.number().int().positive(),
})

const removeCartItemSchema = z.object({
  itemId: z.string().uuid(),
})

type CartRow = {
  id: string
  quantity: number
  product: Product | Product[] | null
}

function normalizeProduct(product: Product | Product[] | null): Product {
  if (!product) throw new Error('Product not found')
  return Array.isArray(product) ? product[0] : product
}

function mapCartRows(rows: CartRow[]): CartPayload {
  const items: CartLine[] = rows.map((row) => {
    const product = normalizeProduct(row.product)
    const price = Number(product.price)
    return {
      id: row.id,
      quantity: row.quantity,
      product: { ...product, price },
      subtotal: price * row.quantity,
    }
  })

  const itemCount = items.reduce((sum, item) => sum + item.quantity, 0)
  const subtotal = items.reduce((sum, item) => sum + item.subtotal, 0)

  return { items, itemCount, subtotal }
}

async function fetchCartForUser(
  supabase: ReturnType<typeof createSupabaseServerClient>,
  userId: string,
): Promise<CartPayload> {
  const { data, error } = await supabase
    .from('cart_items')
    .select(
      `
        id,
        quantity,
        product:products (
          id,
          title,
          description,
          price,
          image_url,
          seller_name,
          stock
        )
      `,
    )
    .eq('user_id', userId)
    .order('created_at', { ascending: true })

  if (error) throw new Error(error.message)
  return mapCartRows((data ?? []) as CartRow[])
}

export const getCart = createServerFn({ method: 'GET' })
  .middleware([requireSupabaseAuth])
  .handler(async ({ context }) => {
    return fetchCartForUser(context.supabase, context.user.id)
  })

export const addToCart = createServerFn({ method: 'POST' })
  .middleware([requireSupabaseAuth])
  .validator(addToCartSchema)
  .handler(async ({ context, data }) => {
    const { supabase, user } = context

    const { data: product, error: productError } = await supabase
      .from('products')
      .select('id, stock, price, title, description, image_url, seller_name')
      .eq('id', data.productId)
      .single()

    if (productError || !product) throw new Error('Producto no encontrado')
    if (product.stock < 1) throw new Error('Producto sin stock')

    const { data: existing, error: existingError } = await supabase
      .from('cart_items')
      .select('id, quantity')
      .eq('user_id', user.id)
      .eq('product_id', data.productId)
      .maybeSingle()

    if (existingError) throw new Error(existingError.message)

    const nextQuantity = (existing?.quantity ?? 0) + data.quantity
    if (nextQuantity > product.stock) {
      throw new Error(`Solo hay ${product.stock} unidades disponibles`)
    }

    if (existing) {
      const { error: updateError } = await supabase
        .from('cart_items')
        .update({ quantity: nextQuantity })
        .eq('id', existing.id)
        .eq('user_id', user.id)

      if (updateError) throw new Error(updateError.message)
    } else {
      const { error: insertError } = await supabase.from('cart_items').insert({
        user_id: user.id,
        product_id: data.productId,
        quantity: data.quantity,
      })

      if (insertError) throw new Error(insertError.message)
    }

    return fetchCartForUser(supabase, user.id)
  })

export const updateCartItem = createServerFn({ method: 'POST' })
  .middleware([requireSupabaseAuth])
  .validator(updateCartItemSchema)
  .handler(async ({ context, data }) => {
    const { supabase, user } = context

    const { data: item, error: itemError } = await supabase
      .from('cart_items')
      .select(
        `
          id,
          quantity,
          product:products ( stock )
        `,
      )
      .eq('id', data.itemId)
      .eq('user_id', user.id)
      .single()

    if (itemError || !item) throw new Error('Artículo no encontrado en el carrito')

    const product = normalizeProduct(item.product as Product | Product[] | null)
    if (data.quantity > product.stock) {
      throw new Error(`Solo hay ${product.stock} unidades disponibles`)
    }

    const { error: updateError } = await supabase
      .from('cart_items')
      .update({ quantity: data.quantity })
      .eq('id', data.itemId)
      .eq('user_id', user.id)

    if (updateError) throw new Error(updateError.message)

    return fetchCartForUser(supabase, user.id)
  })

export const removeCartItem = createServerFn({ method: 'POST' })
  .middleware([requireSupabaseAuth])
  .validator(removeCartItemSchema)
  .handler(async ({ context, data }) => {
    const { supabase, user } = context

    const { error } = await supabase
      .from('cart_items')
      .delete()
      .eq('id', data.itemId)
      .eq('user_id', user.id)

    if (error) throw new Error(error.message)

    return fetchCartForUser(supabase, user.id)
  })

export const clearCart = createServerFn({ method: 'POST' })
  .middleware([requireSupabaseAuth])
  .handler(async ({ context }) => {
    const { supabase, user } = context

    const { error } = await supabase.from('cart_items').delete().eq('user_id', user.id)
    if (error) throw new Error(error.message)

    return fetchCartForUser(supabase, user.id)
  })

export const getProducts = createServerFn({ method: 'GET' }).handler(async () => {
  const supabase = createSupabaseServerClient()
  const { data, error } = await supabase
    .from('products')
    .select('id, title, description, price, image_url, seller_name, stock')
    .order('created_at', { ascending: true })

  if (error) throw new Error(error.message)

  return (data ?? []).map((product) => ({
    ...product,
    price: Number(product.price),
  })) satisfies Product[]
})

export const getSession = createServerFn({ method: 'GET' }).handler(async () => {
  const supabase = createSupabaseServerClient()
  const {
    data: { user },
  } = await supabase.auth.getUser()

  return {
    user: user
      ? {
          id: user.id,
          email: user.email ?? '',
        }
      : null,
  }
})

export const signInWithPassword = createServerFn({ method: 'POST' })
  .validator(
    z.object({
      email: z.string().email(),
      password: z.string().min(6),
    }),
  )
  .handler(async ({ data }) => {
    const supabase = createSupabaseServerClient()
    const { error } = await supabase.auth.signInWithPassword({
      email: data.email,
      password: data.password,
    })
    if (error) throw new Error(error.message)
    return { ok: true as const }
  })

export const signUpWithPassword = createServerFn({ method: 'POST' })
  .validator(
    z.object({
      email: z.string().email(),
      password: z.string().min(6),
    }),
  )
  .handler(async ({ data }) => {
    const supabase = createSupabaseServerClient()
    const { error } = await supabase.auth.signUp({
      email: data.email,
      password: data.password,
    })
    if (error) throw new Error(error.message)
    return { ok: true as const }
  })

export const signOut = createServerFn({ method: 'POST' }).handler(async () => {
  const supabase = createSupabaseServerClient()
  const { error } = await supabase.auth.signOut()
  if (error) throw new Error(error.message)
  return { ok: true as const }
})
