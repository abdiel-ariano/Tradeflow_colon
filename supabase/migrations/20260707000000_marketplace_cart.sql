-- Marketplace products + cart (Supabase public schema)
-- Run via Supabase CLI or SQL editor.

create table if not exists public.products (
  id uuid primary key default gen_random_uuid(),
  title text not null,
  description text,
  price numeric(10, 2) not null,
  image_url text,
  seller_name text,
  stock integer not null default 0,
  created_at timestamptz not null default now()
);

create table if not exists public.cart_items (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users (id) on delete cascade,
  product_id uuid not null references public.products (id) on delete cascade,
  quantity integer not null check (quantity > 0),
  created_at timestamptz not null default now(),
  unique (user_id, product_id)
);

-- Grants
grant select on table public.products to anon, authenticated;
grant all on table public.products to service_role;

grant select, insert, update, delete on table public.cart_items to authenticated;
grant all on table public.cart_items to service_role;

-- RLS
alter table public.products enable row level security;
alter table public.cart_items enable row level security;

drop policy if exists "products_public_read" on public.products;
create policy "products_public_read"
  on public.products
  for select
  to anon, authenticated
  using (true);

drop policy if exists "cart_items_select_own" on public.cart_items;
create policy "cart_items_select_own"
  on public.cart_items
  for select
  to authenticated
  using (user_id = auth.uid());

drop policy if exists "cart_items_insert_own" on public.cart_items;
create policy "cart_items_insert_own"
  on public.cart_items
  for insert
  to authenticated
  with check (user_id = auth.uid());

drop policy if exists "cart_items_update_own" on public.cart_items;
create policy "cart_items_update_own"
  on public.cart_items
  for update
  to authenticated
  using (user_id = auth.uid())
  with check (user_id = auth.uid());

drop policy if exists "cart_items_delete_own" on public.cart_items;
create policy "cart_items_delete_own"
  on public.cart_items
  for delete
  to authenticated
  using (user_id = auth.uid());

-- Seed (idempotent by title)
insert into public.products (title, description, price, image_url, seller_name, stock)
select * from (
  values
    (
      'Auriculares Bluetooth Pro',
      'Cancelación de ruido activa y 30 h de batería.',
      89.99::numeric(10, 2),
      'https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=400&h=400&fit=crop',
      'TechPanama',
      42
    ),
    (
      'Teclado Mecánico RGB',
      'Switches hot-swap y retroiluminación personalizable.',
      129.50::numeric(10, 2),
      'https://images.unsplash.com/photo-1587829741301-dc798b83add3?w=400&h=400&fit=crop',
      'Periféricos CR',
      28
    ),
    (
      'Monitor 27" 4K',
      'Panel IPS, 144 Hz, ideal para productividad y gaming.',
      349.00::numeric(10, 2),
      'https://images.unsplash.com/photo-1527443224154-c4a3942d3acf?w=400&h=400&fit=crop',
      'DisplayMax',
      15
    ),
    (
      'Silla Ergonómica Oficina',
      'Soporte lumbar ajustable y reposabrazos 4D.',
      279.99::numeric(10, 2),
      'https://images.unsplash.com/photo-1580480055273-228ff5388ef8?w=400&h=400&fit=crop',
      'Mobiliario Express',
      20
    ),
    (
      'Cafetera Espresso Automática',
      'Molienda integrada y espumador de leche.',
      199.00::numeric(10, 2),
      'https://images.unsplash.com/photo-1495474472287-4d71bcdd2085?w=400&h=400&fit=crop',
      'Hogar & Sabor',
      33
    ),
    (
      'Mochila Antirrobo Urban',
      'Puerto USB, compartimento para laptop 16" y material impermeable.',
      59.90::numeric(10, 2),
      'https://images.unsplash.com/photo-1553062407-98eeb64c6a62?w=400&h=400&fit=crop',
      'Urban Gear PA',
      55
    )
) as seed (title, description, price, image_url, seller_name, stock)
where not exists (
  select 1 from public.products p where p.title = seed.title
);
