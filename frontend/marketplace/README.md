# TradeFlow Marketplace (TanStack Start + Supabase cart)

Full-stack shopping cart demo with:

- Supabase `products` + `cart_items` tables (see `/workspace/supabase/migrations/20260707000000_marketplace_cart.sql`)
- Server functions in `src/lib/cart.functions.ts`
- Routes: `/`, `/cart`, `/auth`
- TanStack Query cache key `["cart"]`

## Setup

```bash
cd frontend/marketplace
cp .env.example .env
npm install
```

Apply the SQL migration in your Supabase project, then:

```bash
npm run dev
```

Open http://localhost:3000

## Scripts

- `npm run dev` — development server
- `npm run generate-routes` — regenerate `src/routeTree.gen.ts`
- `npm run build` — production build

## Auth + cart

Protected server functions use `requireSupabaseAuth` middleware. The `/cart` route loads data with `useServerFn` + `useQuery` (not public loaders).
