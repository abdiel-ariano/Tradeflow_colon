import { formatPrice, formatSold, type Product } from '@/lib/catalog-data';

interface ProductCardProps {
  product: Product;
  onAddToInquiry: () => void;
}

export function ProductCard({ product, onAddToInquiry }: ProductCardProps) {
  return (
    <article className="group relative flex h-[320px] flex-col overflow-hidden rounded-[6px] border border-border bg-white transition-shadow hover:shadow-md">
      <div
        className="relative flex h-[180px] shrink-0 items-center justify-center rounded-t-[6px]"
        style={{ backgroundColor: product.bg }}
      >
        <span className="text-5xl" role="img" aria-hidden="true">
          {product.emoji}
        </span>

        <div className="absolute left-2 top-2 flex flex-col gap-1">
          {product.verified && (
            <span className="rounded-[4px] bg-emerald px-1.5 py-0.5 text-[10px] font-semibold text-white">
              CFZ Verified
            </span>
          )}
          {product.discount && (
            <span className="rounded-[4px] bg-danger px-1.5 py-0.5 text-[10px] font-semibold text-white">
              -{product.discount}%
            </span>
          )}
        </div>
      </div>

      <div className="flex flex-1 flex-col p-3">
        <h3 className="line-clamp-2 text-[13px] leading-tight text-text-primary">
          {product.name}
        </h3>

        <p className="mt-1.5 text-[18px] font-bold text-navy">
          {formatPrice(product.priceMin, product.priceMax)}
        </p>

        <p className="mt-1 text-[11px] text-text-secondary">
          MOQ: {product.moq} {product.moqUnit}
        </p>

        <p className="text-[11px] text-text-muted">{formatSold(product.sold)}</p>

        <div className="mt-auto flex items-center gap-1.5 pt-2">
          <span className="text-[12px]" role="img" aria-label={product.country}>
            {product.flag}
          </span>
          <span className="text-[11px] text-text-secondary">{product.country}</span>
          <span className="text-[11px] text-text-muted">·</span>
          <span className="text-[11px] text-text-muted">{product.years} yrs</span>
          <span className="ml-auto rounded-[4px] bg-surface px-1.5 py-0.5 text-[10px] font-medium text-navy-mid">
            {product.reorderRate}% reorder
          </span>
        </div>
      </div>

      <button
        type="button"
        onClick={onAddToInquiry}
        className="absolute bottom-0 left-0 right-0 flex h-8 translate-y-full items-center justify-center bg-orange text-[12px] font-semibold text-white transition-transform duration-150 group-hover:translate-y-0"
      >
        + Add to inquiry
      </button>
    </article>
  );
}
