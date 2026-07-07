import { createServerClient, parseCookieHeader, serializeCookieHeader } from '@supabase/ssr'
import type { SerializeOptions } from 'cookie'
import type { SupabaseClient } from '@supabase/supabase-js'
import { getRequest } from '@tanstack/react-start/server'

function requireEnv(name: string) {
  const value = process.env[name]
  if (!value) throw new Error(`Missing environment variable: ${name}`)
  return value
}

export function createSupabaseServerClient(): SupabaseClient {
  const request = getRequest()
  const headers = new Headers()
  const cookieHeader = request.headers.get('cookie') ?? ''

  const supabase = createServerClient(
    requireEnv('SUPABASE_URL'),
    requireEnv('SUPABASE_ANON_KEY'),
    {
      cookies: {
        getAll() {
          return parseCookieHeader(cookieHeader).map((cookie) => ({
            name: cookie.name,
            value: cookie.value ?? '',
          }))
        },
        setAll(cookiesToSet: { name: string; value: string; options?: SerializeOptions }[]) {
          cookiesToSet.forEach(({ name, value, options }) => {
            headers.append('Set-Cookie', serializeCookieHeader(name, value, options ?? {}))
          })
        },
      },
    },
  )

  return supabase
}

export async function getSupabaseSessionUser(supabase: SupabaseClient) {
  const {
    data: { user },
    error,
  } = await supabase.auth.getUser()

  if (error || !user) {
    throw new Error('Unauthorized')
  }

  return user
}
