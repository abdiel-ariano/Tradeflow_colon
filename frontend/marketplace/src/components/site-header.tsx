import { Link } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import { useServerFn } from '@tanstack/react-start'
import { LogOut, ShoppingCart, Store, UserRound } from 'lucide-react'
import { getCart, getSession, signOut } from '@/lib/cart.functions'
import { cartQueryKey, sessionQueryKey } from '@/lib/query-client'
import { Button } from '@/components/ui/button'
import { useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'

export function SiteHeader() {
  const queryClient = useQueryClient()
  const getSessionFn = useServerFn(getSession)
  const getCartFn = useServerFn(getCart)
  const signOutFn = useServerFn(signOut)

  const sessionQuery = useQuery({
    queryKey: sessionQueryKey,
    queryFn: () => getSessionFn(),
  })

  const isAuthenticated = Boolean(sessionQuery.data?.user)

  const cartQuery = useQuery({
    queryKey: cartQueryKey,
    queryFn: () => getCartFn(),
    enabled: isAuthenticated,
  })

  const cartCount = cartQuery.data?.itemCount ?? 0

  async function handleSignOut() {
    try {
      await signOutFn()
      queryClient.setQueryData(sessionQueryKey, { user: null })
      queryClient.removeQueries({ queryKey: cartQueryKey })
      toast.success('Sesión cerrada')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'No se pudo cerrar sesión')
    }
  }

  return (
    <header className="sticky top-0 z-40 border-b border-border bg-card/95 backdrop-blur supports-[backdrop-filter]:bg-card/80">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-4 px-4 sm:px-6">
        <div className="flex items-center gap-6">
          <Link to="/" className="flex items-center gap-2 font-bold text-foreground">
            <Store className="h-5 w-5 text-primary" aria-hidden />
            <span>TradeFlow Market</span>
          </Link>
          <nav className="hidden items-center gap-4 text-sm font-medium sm:flex">
            <Link
              to="/"
              className="text-muted-foreground transition-colors hover:text-foreground"
              activeProps={{ className: 'text-foreground' }}
            >
              Productos
            </Link>
            <Link
              to="/cart"
              className="text-muted-foreground transition-colors hover:text-foreground"
              activeProps={{ className: 'text-foreground' }}
            >
              Carrito
            </Link>
          </nav>
        </div>

        <div className="flex items-center gap-2">
          {isAuthenticated ? (
            <>
              <Link
                to="/cart"
                className="relative inline-flex h-10 w-10 items-center justify-center rounded-md border border-border bg-card hover:bg-muted"
                aria-label={`Carrito con ${cartCount} artículos`}
              >
                <ShoppingCart className="h-5 w-5" />
                {cartCount > 0 ? (
                  <span className="absolute -right-1 -top-1 inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-primary px-1 text-[11px] font-bold text-primary-foreground">
                    {cartCount > 99 ? '99+' : cartCount}
                  </span>
                ) : null}
              </Link>
              <div className="hidden items-center gap-2 sm:flex">
                <span className="max-w-[180px] truncate text-sm text-muted-foreground">
                  {sessionQuery.data?.user?.email}
                </span>
                <Button variant="outline" size="sm" onClick={handleSignOut}>
                  <LogOut className="h-4 w-4" />
                  Salir
                </Button>
              </div>
            </>
          ) : (
            <Button asChild variant="default" size="sm">
              <Link to="/auth">
                <UserRound className="h-4 w-4" />
                Iniciar sesión
              </Link>
            </Button>
          )}
        </div>
      </div>
    </header>
  )
}

export function SiteFooter() {
  return (
    <footer className="border-t border-border bg-card">
      <div className="mx-auto max-w-7xl px-4 py-6 text-sm text-muted-foreground sm:px-6">
        © {new Date().getFullYear()} TradeFlow Market — Compra segura tipo marketplace.
      </div>
    </footer>
  )
}
