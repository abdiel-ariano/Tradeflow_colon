import { QueryClient } from '@tanstack/react-query'

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
    },
  },
})

export const cartQueryKey = ['cart'] as const
export const sessionQueryKey = ['session'] as const
export const productsQueryKey = ['products'] as const
