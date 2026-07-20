# Product reference images

TradeFlow uses consistent studio-style reference images when demo products do
not yet have real supplier media. These assets describe a concrete product
family; they are not presented as photos from a supplier.

## Prompt base

- White or neutral gray background (`#F7F8FA`)
- Neutral commercial product photography
- Studio lighting and a soft shadow
- Product centered at a three-quarter angle
- No logos, brands, watermarks, labels, or overlaid text
- 4:3 landscape composition

## File convention

Shared family references live under:

```
static/assets/products/reference/<product-family>.webp
```

The mapping from normalized product names to files is defined in
`core.utils.demo_product_images.PRODUCT_REFERENCE_MATCHES`.

Exact-SKU legacy assets under
`static/assets/products/placeholder-ai/{category}-{sku}.webp` remain
supported for backwards compatibility.

## Runtime resolution

`product_image_src` resolves in this order:

1. A concrete family reference when the current image is missing or demo-generated
2. A real supplier upload (`Product.image`)
3. An exact-SKU legacy reference
4. Optional Picsum only when explicitly enabled for development
5. A category SVG icon, never an unrelated category photograph

Cards show a discrete **"Reference image"** label whenever a generated reference
is used. A future supplier upload automatically replaces the reference.

## Current textile and accessory coverage

The demo catalog currently resolves these wholesale clothing families to local
reference assets:

- `industrial-cargo-pants.webp`: Industrial Cargo Pants.
- `corporate-dry-fit-polo.webp`: Corporate Dry-Fit Polo.
- `staff-waterproof-jacket.webp`: Staff Waterproof Jacket.
- `hospitality-set-300-thread.webp`: 300-Thread Hospitality Set.
- `rigid-executive-briefcase.webp`: Rigid Executive Briefcase.
- `top-grain-leather-belt.webp`: Top-Grain Leather Belt.
- `travel-organizer-set.webp`: Travel Organizer Set.

Clothing references use a ghost-mannequin composition. Linen and accessory
references use isolated product compositions without visible people, logos,
text, labels, or brand marks. This keeps the demo commercially neutral
until real suppliers provide approved product photography.

## Current appliance, desk, and packaging coverage

The following demo families also resolve to packaged product photography:

- `industrial-blender-2l.webp`: 2L Industrial Blender.
- `digital-air-fryer-8l.webp`: 8L Digital Air Fryer.
- `adjustable-led-floor-lamp.webp`: Adjustable LED Floor Lamp.
- `xl-stitched-edge-pad.webp`: XL Stitched Edge Pad.
- `clear-pp-packing-tape.webp`: 48mm x 150m Clear PP Tape.
- `manual-stretch-film-20.webp`: 20-inch Manual Stretch Film.

These references use isolated, unbranded product compositions. They prevent
empty catalog cards when simulated media files are unavailable in a deployment.
Real supplier uploads continue to take precedence.
