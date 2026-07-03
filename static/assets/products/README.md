# AI product placeholder images

TradeFlow uses consistent studio-style reference photos when suppliers have not uploaded real assets.

## Prompt base (all categories)

- White or neutral gray background (`#F7F8FA`, matching `--color-background`)
- Studio lighting, soft shadow
- Product at 3/4 angle
- No third-party watermarks
- No overlaid text in the image file

## File convention

Place WebP files under:

```
static/assets/products/placeholder-ai/{categoria}-{sku}.webp
```

Examples:

- `electronics-elec-sony-002.webp`
- `textiles-text-lino-001.webp`

The `{categoria}` keyword matches `core.utils.demo_product_images.category_keyword()`:
`electronics`, `textiles`, `beauty`, `home_appliances`, `toys`, `general`.

## Runtime resolution

`product_image_src` resolves in order:

1. Supplier upload (`Product.image`)
2. AI placeholder WebP at the path above (if the file exists)
3. Category SVG icon (`static/images/category-icons/{categoria}.svg`)

Cards show a discrete **"Reference image"** label when option 2 is used.

## Style rule

Do not mix illustration, photo, and 3D-render styles within the same visible catalog row.
