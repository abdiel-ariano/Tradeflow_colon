import { createFileRoute, Link } from '@tanstack/react-router'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useServerFn } from '@tanstack/react-start'
import {
  Lock,
  Minus,
  Package,
  Plus,
  RotateCcw,
  ShoppingCart,
  Trash2,
} from 'lucide-react'
import { toast } from 'sonner'
import {
  clearCart,
  getCart,
  getSession,
  removeCartItem,
  updateCartItem,
} from '@/lib/cart.functions'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { cartQueryKey, sessionQueryKey } from '@/lib/query-client'
import { calcOrderTotals, formatUsd } from '@/lib/utils'

export const Route = createFileRoute('/cart')({
  head: () => ({
    meta: [
      { title: 'Carrito de compras — TradeFlow Market' },
      {
        name: 'description',
        content: 'Revisa tu carrito, ajusta cantidades y finaliza tu compra.',
      },
      { property: 'og:title', content: 'Carrito de compras — TradeFlow Market' },
      {
        property: 'og:description',
        content: 'Revisa tu carrito, ajusta cantidades y finaliza tu compra.',
      },
      { property: 'og:type', content: 'website' },
    ],
  }),
  component: CartPage,
  errorComponent: CartError,
  notFoundComponent: CartNotFound,
})

function CartPage() {
  const queryClient = useQueryClient()
  const getSessionFn = useServerFn(getSession)
  const getCartFn = useServerFn(getCart)
  const updateCartItemFn = useServerFn(updateCartItem)
  const removeCartItemFn = useServerFn(removeCartItem)
  const clearCartFn = useServerFn(clearCart)

  const sessionQuery = useQuery({
    queryKey: sessionQueryKey,
    queryFn: () => getSessionFn(),
  })

  const cartQuery = useQuery({
    queryKey: cartQueryKey,
    queryFn: () => getCartFn(),
    enabled: Boolean(sessionQuery.data?.user),
  })

  const updateMutation = useMutation({
    mutationFn: (payload: { itemId: string; quantity: number }) =>
      updateCartItemFn({ data: payload }),
    onSuccess: (cart) => {
      queryClient.setQueryData(cartQueryKey, cart)
    },
    onError: (error: Error) => toast.error(error.message),
  })

  const removeMutation = useMutation({
    mutationFn: (itemId: string) => removeCartItemFn({ data: { itemId } }),
    onSuccess: (cart) => {
      queryClient.setQueryData(cartQueryKey, cart)
      toast.success('Producto eliminado')
    },
    onError: (error: Error) => toast.error(error.message),
  })

  const clearMutation = useMutation({
    mutationFn: () => clearCartFn(),
    onSuccess: (cart) => {
      queryClient.setQueryData(cartQueryKey, cart)
      toast.success('Carrito vaciado')
    },
    onError: (error: Error) => toast.error(error.message),
  })

  if (sessionQuery.isLoading) {
    return <CartSkeleton />
  }

  if (!sessionQuery.data?.user) {
    return (
      <div className="mx-auto flex max-w-lg flex-col items-center gap-4 px-4 py-20 text-center">
        <ShoppingCart className="h-16 w-16 text-muted-foreground" />
        <h1 className="text-2xl font-bold">Inicia sesión para ver tu carrito</h1>
        <p className="text-muted-foreground">Guarda tus productos y continúa la compra cuando quieras.</p>
        <Button asChild size="lg">
          <Link to="/auth">Iniciar sesión</Link>
        </Button>
      </div>
    )
  }

  if (cartQuery.isLoading) {
    return <CartSkeleton />
  }

  const cart = cartQuery.data
  const items = cart?.items ?? []
  const totals = calcOrderTotals(cart?.subtotal ?? 0)

  if (items.length === 0) {
    return (
      <div className="mx-auto flex max-w-lg flex-col items-center gap-4 px-4 py-20 text-center">
        <ShoppingCart className="h-20 w-20 text-muted-foreground" />
        <h1 className="text-2xl font-bold">Tu carrito está vacío</h1>
        <p className="text-muted-foreground">Explora el catálogo y agrega productos para comenzar.</p>
        <Button asChild size="lg">
          <Link to="/">Ver productos</Link>
        </Button>
      </div>
    )
  }

  return (
    <TooltipProvider>
      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
          <section className="lg:col-span-8">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
              <div>
                <h1 className="text-2xl font-bold">Carrito de compras</h1>
                <p className="text-sm text-muted-foreground">{cart?.itemCount ?? 0} artículos</p>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => clearMutation.mutate()}
                disabled={clearMutation.isPending}
                loading={clearMutation.isPending}
              >
                <Trash2 className="h-4 w-4" />
                Vaciar carrito
              </Button>
            </div>

            <div className="space-y-4">
              {items.map((item, index) => (
                <div key={item.id}>
                  <Card className="overflow-hidden">
                    <CardContent className="flex flex-col gap-4 p-4 sm:flex-row sm:items-center">
                      <div className="h-24 w-24 shrink-0 overflow-hidden rounded-md bg-muted">
                        {item.product.image_url ? (
                          <img
                            src={item.product.image_url}
                            alt={item.product.title}
                            className="h-24 w-24 object-cover"
                          />
                        ) : (
                          <div className="flex h-full items-center justify-center">
                            <Package className="h-8 w-8 text-muted-foreground" />
                          </div>
                        )}
                      </div>

                      <div className="min-w-0 flex-1 space-y-1">
                        <h2 className="font-semibold leading-tight">{item.product.title}</h2>
                        <p className="text-sm text-muted-foreground">
                          Vendido por {item.product.seller_name ?? 'Marketplace'}
                        </p>
                        <p className="text-sm font-medium">{formatUsd(item.product.price)} c/u</p>
                      </div>

                      <div className="flex flex-col items-start gap-3 sm:items-end">
                        <div className="flex items-center gap-2">
                          <Button
                            variant="outline"
                            size="icon"
                            aria-label="Disminuir cantidad"
                            disabled={item.quantity <= 1 || updateMutation.isPending}
                            onClick={() =>
                              updateMutation.mutate({
                                itemId: item.id,
                                quantity: item.quantity - 1,
                              })
                            }
                          >
                            <Minus className="h-4 w-4" />
                          </Button>
                          <Input
                            type="number"
                            min={1}
                            max={item.product.stock}
                            value={item.quantity}
                            className="w-16 text-center"
                            onChange={(event) => {
                              const next = Number(event.target.value)
                              if (!Number.isFinite(next)) return
                              updateMutation.mutate({ itemId: item.id, quantity: next })
                            }}
                          />
                          <Button
                            variant="outline"
                            size="icon"
                            aria-label="Aumentar cantidad"
                            disabled={
                              item.quantity >= item.product.stock || updateMutation.isPending
                            }
                            onClick={() =>
                              updateMutation.mutate({
                                itemId: item.id,
                                quantity: item.quantity + 1,
                              })
                            }
                          >
                            <Plus className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            aria-label="Eliminar producto"
                            disabled={removeMutation.isPending}
                            onClick={() => removeMutation.mutate(item.id)}
                          >
                            <Trash2 className="h-4 w-4 text-destructive" />
                          </Button>
                        </div>
                        <p className="text-base font-semibold">{formatUsd(item.subtotal)}</p>
                      </div>
                    </CardContent>
                  </Card>
                  {index < items.length - 1 ? <div className="my-4 h-px bg-border" /> : null}
                </div>
              ))}
            </div>
          </section>

          <aside className="space-y-4 lg:col-span-4">
            <Card className="sticky top-24">
              <CardHeader>
                <CardTitle>Resumen del pedido</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 text-sm">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Subtotal</span>
                  <span className="font-medium">{formatUsd(totals.subtotal)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Envío</span>
                  <span className="font-medium">
                    {totals.shipping === 0 ? 'Gratis' : formatUsd(totals.shipping)}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Impuestos (16% IVA)</span>
                  <span className="font-medium">{formatUsd(totals.taxes)}</span>
                </div>
                <div className="h-px bg-border" />
                <div className="flex items-center justify-between">
                  <span className="text-base font-semibold">Total</span>
                  <span className="text-2xl font-bold">{formatUsd(totals.total)}</span>
                </div>

                <Tooltip>
                  <TooltipTrigger asChild>
                    <span className="block w-full">
                      <Button className="w-full" size="lg" disabled>
                        Finalizar compra
                      </Button>
                    </span>
                  </TooltipTrigger>
                  <TooltipContent>Próximamente</TooltipContent>
                </Tooltip>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base">Métodos de pago</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex flex-wrap gap-2">
                  {['Visa', 'Mastercard', 'Amex', 'PayPal', 'Apple Pay', 'Google Pay'].map(
                    (method) => (
                      <Badge key={method} variant="outline">
                        {method}
                      </Badge>
                    ),
                  )}
                </div>
                <p className="flex items-center gap-2 text-xs text-muted-foreground">
                  <Lock className="h-4 w-4 shrink-0" />
                  Pago 100% seguro y encriptado
                </p>
                <p className="flex items-center gap-2 text-xs text-muted-foreground">
                  <RotateCcw className="h-4 w-4 shrink-0" />
                  30 días para devoluciones
                </p>
              </CardContent>
            </Card>
          </aside>
        </div>
      </div>
    </TooltipProvider>
  )
}

function CartSkeleton() {
  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
      <Skeleton className="mb-6 h-8 w-56" />
      <div className="grid gap-6 lg:grid-cols-12">
        <div className="space-y-4 lg:col-span-8">
          {Array.from({ length: 3 }).map((_, index) => (
            <Card key={index}>
              <CardContent className="flex gap-4 p-4">
                <Skeleton className="h-24 w-24" />
                <div className="flex-1 space-y-2">
                  <Skeleton className="h-5 w-2/3" />
                  <Skeleton className="h-4 w-1/3" />
                  <Skeleton className="h-4 w-24" />
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
        <div className="lg:col-span-4">
          <Card>
            <CardContent className="space-y-3 p-6">
              <Skeleton className="h-5 w-40" />
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-10 w-full" />
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}

function CartError({ error }: { error: Error }) {
  return (
    <div className="mx-auto max-w-lg px-4 py-20 text-center">
      <h2 className="text-xl font-semibold">No se pudo cargar el carrito</h2>
      <p className="mt-2 text-sm text-muted-foreground">{error.message}</p>
    </div>
  )
}

function CartNotFound() {
  return (
    <div className="mx-auto max-w-lg px-4 py-20 text-center">
      <h2 className="text-xl font-semibold">Carrito no encontrado</h2>
    </div>
  )
}
