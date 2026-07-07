import { createFileRoute, Link } from '@tanstack/react-router'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useServerFn } from '@tanstack/react-start'
import { ShoppingCart } from 'lucide-react'
import { toast } from 'sonner'
import { addToCart, getProducts, getSession } from '@/lib/cart.functions'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { cartQueryKey, productsQueryKey, sessionQueryKey } from '@/lib/query-client'
import { formatUsd } from '@/lib/utils'

export const Route = createFileRoute('/')({
  head: () => ({
    meta: [
      { title: 'Productos — TradeFlow Market' },
      {
        name: 'description',
        content: 'Explora productos destacados y agrégalos a tu carrito.',
      },
      { property: 'og:title', content: 'Productos — TradeFlow Market' },
      {
        property: 'og:description',
        content: 'Explora productos destacados y agrégalos a tu carrito.',
      },
      { property: 'og:type', content: 'website' },
    ],
  }),
  component: ProductsPage,
  errorComponent: ProductsError,
})

function ProductsPage() {
  const queryClient = useQueryClient()
  const getProductsFn = useServerFn(getProducts)
  const getSessionFn = useServerFn(getSession)
  const addToCartFn = useServerFn(addToCart)

  const sessionQuery = useQuery({
    queryKey: sessionQueryKey,
    queryFn: () => getSessionFn(),
  })

  const productsQuery = useQuery({
    queryKey: productsQueryKey,
    queryFn: () => getProductsFn(),
  })

  const addMutation = useMutation({
    mutationFn: (productId: string) => addToCartFn({ data: { productId, quantity: 1 } }),
    onSuccess: (cart) => {
      queryClient.setQueryData(cartQueryKey, cart)
      toast.success('Producto agregado al carrito')
    },
    onError: (error: Error) => toast.error(error.message),
  })

  if (productsQuery.isLoading) {
    return <ProductsSkeleton />
  }

  const products = productsQuery.data ?? []

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
      <div className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight">Productos destacados</h1>
        <p className="mt-2 text-muted-foreground">
          Estilo marketplace denso, precios claros y compra rápida.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {products.map((product) => (
          <Card key={product.id} className="overflow-hidden">
            <div className="aspect-[4/3] overflow-hidden bg-muted">
              {product.image_url ? (
                <img
                  src={product.image_url}
                  alt={product.title}
                  className="h-full w-full object-cover"
                  loading="lazy"
                />
              ) : (
                <div className="flex h-full items-center justify-center text-muted-foreground">Sin imagen</div>
              )}
            </div>
            <CardHeader className="pb-2">
              <CardTitle className="line-clamp-2 text-base">{product.title}</CardTitle>
              <CardDescription className="line-clamp-2">{product.description}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-2 pb-2">
              <p className="text-sm text-muted-foreground">Vendido por {product.seller_name ?? 'Marketplace'}</p>
              <p className="text-2xl font-bold">{formatUsd(product.price)}</p>
              <p className="text-xs text-muted-foreground">{product.stock} disponibles</p>
            </CardContent>
            <CardFooter>
              {sessionQuery.data?.user ? (
                <Button
                  className="w-full"
                  disabled={product.stock < 1 || addMutation.isPending}
                  loading={addMutation.isPending}
                  onClick={() => addMutation.mutate(product.id)}
                >
                  <ShoppingCart className="h-4 w-4" />
                  Agregar al carrito
                </Button>
              ) : (
                <Button asChild className="w-full" variant="outline">
                  <Link to="/auth">Inicia sesión para comprar</Link>
                </Button>
              )}
            </CardFooter>
          </Card>
        ))}
      </div>
    </div>
  )
}

function ProductsSkeleton() {
  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
      <Skeleton className="mb-2 h-9 w-64" />
      <Skeleton className="mb-8 h-5 w-96" />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 6 }).map((_, index) => (
          <Card key={index}>
            <Skeleton className="aspect-[4/3] w-full rounded-none" />
            <CardContent className="space-y-2 p-6">
              <Skeleton className="h-5 w-3/4" />
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-8 w-24" />
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}

function ProductsError({ error }: { error: Error }) {
  return (
    <div className="mx-auto max-w-lg px-4 py-20 text-center">
      <h2 className="text-xl font-semibold">No se pudieron cargar los productos</h2>
      <p className="mt-2 text-sm text-muted-foreground">{error.message}</p>
    </div>
  )
}
