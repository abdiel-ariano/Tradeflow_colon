import { ImageIcon, Languages, Search, ShoppingBag } from 'lucide-react';

interface NavbarProps {
  inquiryCount: number;
}

export function Navbar({ inquiryCount }: NavbarProps) {
  return (
    <header className="sticky top-0 z-50 h-16 border-b border-border bg-white">
      <div className="mx-auto flex h-full max-w-[1440px] items-center gap-4 px-4 lg:px-6">
        <a href="/" className="shrink-0 text-[16px] font-semibold text-navy">
          TradeFlow Colón
        </a>

        <div className="relative flex flex-1 max-w-2xl">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted" />
          <input
            type="search"
            placeholder="Search wholesale products, suppliers, SKUs…"
            className="h-10 w-full rounded-[4px] border border-border bg-white pl-10 pr-4 text-[14px] text-text-primary outline-none transition-colors placeholder:text-text-muted focus:border-navy"
          />
        </div>

        <div className="flex shrink-0 items-center gap-2">
          <button
            type="button"
            aria-label="Image search"
            className="flex h-10 w-10 items-center justify-center rounded-[4px] text-navy-mid transition-colors hover:bg-surface"
          >
            <ImageIcon className="h-5 w-5" />
          </button>

          <button
            type="button"
            aria-label="Language"
            className="flex h-10 items-center gap-1 rounded-[4px] px-2 text-[13px] font-medium text-navy-mid transition-colors hover:bg-surface"
          >
            <Languages className="h-4 w-4" />
            EN
          </button>

          <button
            type="button"
            aria-label="Inquiry cart"
            className="relative flex h-10 w-10 items-center justify-center rounded-[4px] text-navy-mid transition-colors hover:bg-surface"
          >
            <ShoppingBag className="h-5 w-5" />
            {inquiryCount > 0 && (
              <span className="absolute -right-0.5 -top-0.5 flex h-[18px] min-w-[18px] items-center justify-center rounded-full bg-orange px-1 text-[10px] font-semibold text-white">
                {inquiryCount > 99 ? '99+' : inquiryCount}
              </span>
            )}
          </button>
        </div>
      </div>
    </header>
  );
}
