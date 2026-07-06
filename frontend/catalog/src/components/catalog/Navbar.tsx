import { useRef, useState } from 'react';
import {
  Camera,
  ChevronDown,
  Menu,
  Search,
  ShoppingCart,
} from 'lucide-react';

interface NavbarProps {
  inquiryCount: number;
}

const RECENT_SEARCHES = [
  'Bluetooth earbuds wholesale',
  'Safety uniforms CFZ',
  'Corrugated boxes export',
];

const FREQUENT_TAGS = ['Smart Watches', 'Mahjong Sets', 'Electronics', 'Workwear'];

const SECONDARY_LINKS = [
  'Verified Companies',
  'Wholesale Catalog',
  'Deals',
  'How it works',
];

export function Navbar({ inquiryCount }: NavbarProps) {
  const [searchFocused, setSearchFocused] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const searchRef = useRef<HTMLDivElement>(null);

  return (
    <header className="sticky top-0 z-50 bg-white">
      {/* Primary nav */}
      <div className="h-16 border-b border-border">
        <div className="mx-auto flex h-full max-w-[1440px] items-center gap-4 px-4 lg:px-6">
          {/* Logo */}
          <a href="/" className="flex shrink-0 items-center gap-2.5">
            <span className="flex h-9 w-9 items-center justify-center rounded-md bg-navy text-[15px] font-bold text-white">
              T
            </span>
            <span className="hidden text-[15px] font-semibold text-navy sm:inline">
              TradeFlow{' '}
              <span className="text-gold">Colón</span>
            </span>
          </a>

          {/* Search — desktop */}
          <div ref={searchRef} className="relative hidden flex-1 lg:block" style={{ maxWidth: 720 }}>
            <div className="flex h-10 overflow-hidden rounded-md border-2 border-navy">
              <input
                type="search"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onFocus={() => setSearchFocused(true)}
                onBlur={() => setTimeout(() => setSearchFocused(false), 150)}
                placeholder="Search wholesale products, suppliers, product codes…"
                className="min-w-0 flex-1 bg-white px-3 text-[14px] text-text-primary outline-none placeholder:text-text-muted focus:ring-1 focus:ring-navy"
              />
              <button
                type="button"
                aria-label="Image search"
                className="flex w-10 shrink-0 items-center justify-center border-l border-border text-navy-mid transition-colors hover:bg-surface"
              >
                <Camera className="h-4 w-4" />
              </button>
              <button
                type="button"
                className="flex shrink-0 items-center gap-1.5 bg-gold px-4 text-[14px] font-semibold text-white transition-colors hover:bg-gold-hover lg:px-6"
              >
                <Search className="h-4 w-4 lg:hidden" />
                <span className="hidden lg:inline">Search</span>
              </button>
            </div>

            {searchFocused && (
              <div className="absolute left-0 right-0 top-[calc(100%+4px)] z-50 rounded-lg border border-border bg-white p-4 shadow-[0_4px_12px_rgba(0,0,0,0.08)]">
                <p className="mb-2 text-[12px] font-semibold text-text-secondary">
                  Recent searches
                </p>
                <ul className="mb-4 space-y-1">
                  {RECENT_SEARCHES.map((term) => (
                    <li key={term}>
                      <button
                        type="button"
                        className="w-full rounded px-2 py-1.5 text-left text-[13px] text-text-primary transition-colors hover:bg-surface"
                      >
                        {term}
                      </button>
                    </li>
                  ))}
                </ul>
                <p className="mb-2 text-[12px] font-semibold text-text-secondary">
                  Frequently searched
                </p>
                <div className="flex flex-wrap gap-2">
                  {FREQUENT_TAGS.map((tag) => (
                    <button
                      key={tag}
                      type="button"
                      className="rounded-full border border-border px-3 py-1 text-[12px] font-medium text-text-secondary transition-colors hover:border-navy hover:text-navy"
                    >
                      {tag}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Right actions — desktop */}
          <div className="ml-auto hidden items-center gap-3 lg:flex">
            <button
              type="button"
              className="flex items-center gap-1 text-[13px] text-text-secondary transition-colors hover:text-navy"
            >
              Deliver to: PA 🇵🇦
              <ChevronDown className="h-3.5 w-3.5" />
            </button>

            <button
              type="button"
              className="text-[13px] font-medium text-navy-mid transition-colors hover:text-navy"
            >
              ES / EN
            </button>

            <button
              type="button"
              aria-label="Inquiry cart"
              className="relative flex h-9 w-9 items-center justify-center rounded-md text-navy-mid transition-colors hover:bg-surface"
            >
              <ShoppingCart className="h-5 w-5" />
              {inquiryCount > 0 && (
                <span className="absolute -right-0.5 -top-0.5 flex h-[18px] min-w-[18px] items-center justify-center rounded-full bg-gold px-1 text-[10px] font-semibold text-white">
                  {inquiryCount > 99 ? '99+' : inquiryCount}
                </span>
              )}
            </button>

            <a
              href="/login"
              className="text-[13px] font-medium text-navy-mid transition-colors hover:text-navy"
            >
              Sign in
            </a>

            <a
              href="/signup"
              className="flex h-9 items-center rounded-md bg-navy px-4 text-[13px] font-semibold text-white transition-colors hover:bg-navy-hover"
            >
              Create account
            </a>
          </div>

          {/* Mobile hamburger */}
          <button
            type="button"
            aria-label="Open menu"
            className="ml-auto flex h-10 w-10 items-center justify-center rounded-md text-navy lg:hidden"
          >
            <Menu className="h-5 w-5" />
          </button>
        </div>
      </div>

      {/* Secondary nav — desktop only */}
      <div className="hidden h-10 border-b border-border bg-surface lg:block">
        <div className="mx-auto flex h-full max-w-[1440px] items-center justify-between px-4 lg:px-6">
          <div className="flex items-center gap-5">
            <button
              type="button"
              className="flex items-center gap-1 text-[13px] font-medium text-navy transition-colors hover:text-navy-mid"
            >
              All categories
              <ChevronDown className="h-3.5 w-3.5" />
            </button>
            {SECONDARY_LINKS.map((link) => (
              <a
                key={link}
                href="#"
                className="text-[13px] text-text-secondary transition-colors hover:text-navy"
              >
                {link}
              </a>
            ))}
          </div>
          <p className="text-[12px] text-text-muted">
            Export docs included · Secure payments · Sell on TradeFlow
          </p>
        </div>
      </div>
    </header>
  );
}
