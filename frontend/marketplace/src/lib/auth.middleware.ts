import { createMiddleware } from '@tanstack/react-start'
import type { SupabaseClient, User } from '@supabase/supabase-js'
import { createSupabaseServerClient, getSupabaseSessionUser } from './supabase.server'

export type AuthContext = {
  supabase: SupabaseClient
  user: User
}

export const requireSupabaseAuth = createMiddleware({ type: 'function' }).server(
  async ({ next }) => {
    const supabase = createSupabaseServerClient()
    const user = await getSupabaseSessionUser(supabase)

    return next({
      context: {
        supabase,
        user,
      } satisfies AuthContext,
    })
  },
)
