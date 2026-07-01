import type { MouseEvent } from 'react';
import { Camera, TrendingDown } from 'lucide-react';
import {
  countryCode,
  formatPrice,
  formatSold,
  type Product,
} from '@/lib/catalog-data';

interface ProductCardProps {
  product: Product;
  onInquiry: () => void;
}

export function ProductCard({ product, onInquiry }: ProductCardProps) {
  const p = product;

  const handleInquiry = (e: MouseEvent) => {
    e.stopPropagation();
    onInquiry();
  };

  return (
    <article className="group relative flex h-[320px] flex-col overflow-hidden rounded-lg border border-border bg-white transition-[border-color,box-shadow] duration-150 hover:border-navy-mid hover:shadow-[0_4px_12px_rgba(0,0,0,0.08)]">
      {/* Image area */}
      <div
        className="relative flex h-[180px] shrink-0 items-center justify-center overflow-hidden"
        style={{ backgroundColor: p.bg }}
      >
        <span className="text-6xl" role="img" aria-hidden="true">
          {p.emoji}
        </span>

        {p.discount && (
          <span className="absolute left-2 top-2 rounded bg-gold px-1.5 py-0.5 text-[10px] font-semibold text-white">
            -{p.discount}%
          </span>
        )}

        <button
          type="button"
          aria-label="View product images"
          className="absolute right-2 top-2 flex h-7 w-7 items-center justify-center rounded border border-border bg-white/90 text-navy-mid transition-colors hover:bg-white"
        >
          <Camera className="h-3.5 w-3.5" />
        </button>
      </div>

      {/* Info */}
      <div className="flex flex-1 flex-col gap-1.5 p-3">
        <h3 className="line-clamp-2 text-[13px] font-medium leading-[1.4] text-text-primary">
          {p.name}
        </h3>

        {/* Trust row */}
        <div className="flex min-h-4 items-center gap-1 text-[11px]">
          {p.reorderRate !== undefined ? (
            <>
              <span className="h-1.5 w-1.5 rounded-full bg-emerald" />
              <span className="text-emerald">Reorder rate {p.reorderRate}%</span>
            </>
          ) : p.lowerPriced ? (
            <>
              <TrendingDown className="h-3 w-3 text-destructive" />
              <span className="text-destructive">Lower priced than similar</span>
            </>
          ) : null}
        </div>

        {/* Price row */}
        <div className="flex flex-wrap items-baseline gap-1.5">
          <span className="text-[18px] font-bold text-navy">
            {formatPrice(p.priceMin, p.priceMax)}
          </span>
          {p.originalPrice && p.discount && (
            <>
              <span className="text-[12px] text-text-muted line-through">
                PAB {p.originalPrice.toFixed(2)}
              </span>
              <span className="text-[11px] font-medium text-destructive">
                {p.discount}% off
              </span>
            </>
          )}
        </div>

        <p className="text-[12px] text-text-secondary">
          MOQ: {p.moq} {p.moqUnit} · {formatSold(p.sold)}
        </p>

        {/* Supplier row */}
        <div className="mt-auto flex items-center justify-between text-[11px]">
          <span className="text-text-muted">
            {p.years}yr · {p.flag} {countryCode(p.country)}
          </span>
          {p.verified && (
            <span className="font-medium text-emerald">🛡 CFZ Verified</span>
          )}
        </div>
      </div>

      {/* Hover action bar */}
      <button
        type="button"
        onClick={handleInquiry}
        className="absolute bottom-0 left-0 right-0 flex h-8 translate-y-full items-center justify-center border-t border-navy bg-white text-[12px] font-semibold text-navy transition-transform duration-150 group-hover:translate-y-0"
      >
        + Add to inquiry
      </button>
    </article>
  );
}
