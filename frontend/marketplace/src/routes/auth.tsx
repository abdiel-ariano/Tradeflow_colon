import { createFileRoute, Link, useNavigate } from '@tanstack/react-router'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useServerFn } from '@tanstack/react-start'
import { useState } from 'react'
import { toast } from 'sonner'
import { signInWithPassword, signUpWithPassword } from '@/lib/cart.functions'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { cartQueryKey, sessionQueryKey } from '@/lib/query-client'

export const Route = createFileRoute('/auth')({
  head: () => ({
    meta: [
      { title: 'Iniciar sesión — TradeFlow Market' },
      {
        name: 'description',
        content: 'Accede a tu cuenta para gestionar tu carrito de compras.',
      },
      { property: 'og:title', content: 'Iniciar sesión — TradeFlow Market' },
      {
        property: 'og:description',
        content: 'Accede a tu cuenta para gestionar tu carrito de compras.',
      },
      { property: 'og:type', content: 'website' },
    ],
  }),
  component: AuthPage,
  errorComponent: AuthError,
  notFoundComponent: AuthNotFound,
})

function AuthPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const signInFn = useServerFn(signInWithPassword)
  const signUpFn = useServerFn(signUpWithPassword)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')

  const signInMutation = useMutation({
    mutationFn: () => signInFn({ data: { email, password } }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: sessionQueryKey })
      await queryClient.invalidateQueries({ queryKey: cartQueryKey })
      toast.success('Bienvenido de nuevo')
      navigate({ to: '/cart' })
    },
    onError: (error: Error) => toast.error(error.message),
  })

  const signUpMutation = useMutation({
    mutationFn: () => signUpFn({ data: { email, password } }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: sessionQueryKey })
      toast.success('Cuenta creada. Revisa tu correo si se requiere confirmación.')
      navigate({ to: '/cart' })
    },
    onError: (error: Error) => toast.error(error.message),
  })

  return (
    <div className="mx-auto flex max-w-md flex-col gap-6 px-4 py-12">
      <div className="text-center">
        <h1 className="text-2xl font-bold">Accede a tu cuenta</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Inicia sesión o regístrate para guardar tu carrito.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Email y contraseña</CardTitle>
          <CardDescription>Integración con Supabase Auth</CardDescription>
        </CardHeader>
        <CardContent>
          <Tabs defaultValue="login">
            <TabsList>
              <TabsTrigger value="login">Iniciar sesión</TabsTrigger>
              <TabsTrigger value="signup">Crear cuenta</TabsTrigger>
            </TabsList>

            <TabsContent value="login" className="space-y-4">
              <AuthForm
                email={email}
                password={password}
                onEmailChange={setEmail}
                onPasswordChange={setPassword}
                submitLabel="Iniciar sesión"
                loading={signInMutation.isPending}
                onSubmit={() => signInMutation.mutate()}
              />
            </TabsContent>

            <TabsContent value="signup" className="space-y-4">
              <AuthForm
                email={email}
                password={password}
                onEmailChange={setEmail}
                onPasswordChange={setPassword}
                submitLabel="Crear cuenta"
                loading={signUpMutation.isPending}
                onSubmit={() => signUpMutation.mutate()}
              />
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>

      <Button asChild variant="ghost">
        <Link to="/">Volver a productos</Link>
      </Button>
    </div>
  )
}

function AuthForm({
  email,
  password,
  onEmailChange,
  onPasswordChange,
  submitLabel,
  loading,
  onSubmit,
}: {
  email: string
  password: string
  onEmailChange: (value: string) => void
  onPasswordChange: (value: string) => void
  submitLabel: string
  loading: boolean
  onSubmit: () => void
}) {
  return (
    <form
      className="space-y-4"
      onSubmit={(event) => {
        event.preventDefault()
        onSubmit()
      }}
    >
      <div className="space-y-2">
        <label htmlFor="email" className="text-sm font-medium">
          Correo electrónico
        </label>
        <Input
          id="email"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(event) => onEmailChange(event.target.value)}
        />
      </div>
      <div className="space-y-2">
        <label htmlFor="password" className="text-sm font-medium">
          Contraseña
        </label>
        <Input
          id="password"
          type="password"
          autoComplete="current-password"
          minLength={6}
          required
          value={password}
          onChange={(event) => onPasswordChange(event.target.value)}
        />
      </div>
      <Button type="submit" className="w-full" size="lg" loading={loading}>
        {submitLabel}
      </Button>
    </form>
  )
}

function AuthError({ error }: { error: Error }) {
  return (
    <div className="mx-auto max-w-lg px-4 py-20 text-center">
      <h2 className="text-xl font-semibold">Error de autenticación</h2>
      <p className="mt-2 text-sm text-muted-foreground">{error.message}</p>
    </div>
  )
}

function AuthNotFound() {
  return (
    <div className="mx-auto max-w-lg px-4 py-20 text-center">
      <h2 className="text-xl font-semibold">Página de auth no encontrada</h2>
    </div>
  )
}
