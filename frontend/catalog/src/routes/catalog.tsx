import { useCallback, useMemo, useState } from 'react';
import { createRoute } from '@tanstack/react-router';
import { Grid3x3, List, SlidersHorizontal, X } from 'lucide-react';
import { CategoryStrip } from '@/components/catalog/CategoryStrip';
import { FilterSidebar } from '@/components/catalog/FilterSidebar';
import { Footer } from '@/components/catalog/Footer';
import { Navbar } from '@/components/catalog/Navbar';
import { ProductCard } from '@/components/catalog/ProductCard';
import { TrustStrip } from '@/components/catalog/TrustStrip';
import {
  PRODUCTS,
  categoryLabel,
  type Product,
} from '@/lib/catalog-data';
import { Route as rootRoute } from './__root';

const CATEGORY_ALIASES: Record<string, string[]> = {
  electronics: ['electronics'],
  textiles: ['textiles'],
  imports: ['general', 'imports'],
  logistics: ['logistics'],
  home: ['home'],
  accessories: ['accessories'],
  automotive: ['automotive'],
  beauty: ['health', 'beauty'],
  industrial: ['construction', 'industrial'],
  food: ['food'],
};

type ViewMode = 'grid' | 'list';

function matchesCategory(productCategory: string, activeId: string | null): boolean {
  if (!activeId) return true;
  const aliases = CATEGORY_ALIASES[activeId] ?? [activeId];
  return aliases.includes(productCategory);
}

function filterProducts(
  items: (Product & { category: string })[],
  activeCategory: string | null,
  trustLevels: Record<string, boolean>,
  minOrder: string,
  supplierTenure: string,
  priceMin: number,
  priceMax: number,
  sortBy: string,
): (Product & { category: string })[] {
  let result = items.filter((p) => matchesCategory(p.category, activeCategory));

  if (trustLevels['cfz-verified']) {
    result = result.filter((p) => p.verified);
  }

  if (minOrder === 'lt50') {
    result = result.filter((p) => p.moq < 50);
  } else if (minOrder === '50-200') {
    result = result.filter((p) => p.moq >= 50 && p.moq <= 200);
  } else if (minOrder === '200+') {
    result = result.filter((p) => p.moq > 200);
  }

  if (supplierTenure !== 'any') {
    const threshold = Number(supplierTenure);
    result = result.filter((p) => p.years >= threshold);
  }

  if (priceMin > 0) {
    result = result.filter((p) => p.priceMin >= priceMin);
  }
  if (priceMax < 500) {
    result = result.filter((p) => (p.priceMax ?? p.priceMin) <= priceMax);
  }

  switch (sortBy) {
    case 'price-asc':
      result.sort((a, b) => a.priceMin - b.priceMin);
      break;
    case 'price-desc':
      result.sort((a, b) => (b.priceMax ?? b.priceMin) - (a.priceMax ?? a.priceMin));
      break;
    case 'sold-desc':
      result.sort((a, b) => b.sold - a.sold);
      break;
    case 'newest':
      result.sort((a, b) => Number(b.id) - Number(a.id));
      break;
  }

  return result;
}

function CatalogPage() {
  const [activeCategory, setActiveCategory] = useState<string | null>('electronics');
  const [inquiryCount, setInquiryCount] = useState(0);
  const [view, setView] = useState<ViewMode>('grid');
  const [mobileFiltersOpen, setMobileFiltersOpen] = useState(false);
  const [sortBy, setSortBy] = useState('relevance');
  const [priceMin, setPriceMin] = useState(0);
  const [priceMax, setPriceMax] = useState(500);
  const [trustLevels, setTrustLevels] = useState<Record<string, boolean>>({
    'cfz-verified': true,
    'export-docs': true,
    'international': false,
  });
  const [minOrder, setMinOrder] = useState('any');
  const [supplierTenure, setSupplierTenure] = useState('any');

  const filteredProducts = useMemo(
    () =>
      filterProducts(
        PRODUCTS,
        activeCategory,
        trustLevels,
        minOrder,
        supplierTenure,
        priceMin,
        priceMax,
        sortBy,
      ),
    [activeCategory, trustLevels, minOrder, supplierTenure, priceMin, priceMax, sortBy],
  );

  const handleInquiry = useCallback(() => {
    setInquiryCount((c) => c + 1);
  }, []);

  const handleTrustToggle = useCallback((key: string) => {
    setTrustLevels((prev) => ({ ...prev, [key]: !prev[key] }));
  }, []);

  const handleClear = useCallback(() => {
    setActiveCategory('electronics');
    setSortBy('relevance');
    setPriceMin(0);
    setPriceMax(500);
    setTrustLevels({ 'cfz-verified': true, 'export-docs': true, international: false });
    setMinOrder('any');
    setSupplierTenure('any');
  }, []);

  const filterProps = {
    activeCategory,
    onCategorySelect: setActiveCategory,
    sortBy,
    onSortChange: setSortBy,
    priceMin,
    priceMax,
    onPriceMinChange: setPriceMin,
    onPriceMaxChange: setPriceMax,
    trustLevels,
    onTrustToggle: handleTrustToggle,
    minOrder,
    onMinOrderChange: setMinOrder,
    supplierTenure,
    onSupplierTenureChange: setSupplierTenure,
    onApply: () => setMobileFiltersOpen(false),
    onClear: handleClear,
  };

  const categoryName = activeCategory ? categoryLabel(activeCategory) : 'All Categories';

  return (
    <div className="min-h-screen bg-white">
      <Navbar inquiryCount={inquiryCount} />
      <CategoryStrip activeCategory={activeCategory} onChange={setActiveCategory} />
      <TrustStrip />

      <div className="mx-auto max-w-[1440px] px-4 py-6 lg:px-6">
        <main className="flex gap-6">
          <div className="hidden shrink-0 lg:block">
            <div className="sticky top-[120px]">
              <FilterSidebar {...filterProps} />
            </div>
          </div>

          <section className="min-w-0 flex-1">
            {/* Results header */}
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
              <p className="text-[14px] text-text-secondary">
                <span className="tabular-nums font-semibold text-navy">
                  {filteredProducts.length}
                </span>{' '}
                products in{' '}
                <span className="font-semibold text-navy">{categoryName}</span>
              </p>

              <div className="flex items-center gap-3">
                <div className="flex overflow-hidden rounded-md border border-border">
                  <button
                    type="button"
                    aria-label="Grid view"
                    onClick={() => setView('grid')}
                    className={`flex h-8 w-8 items-center justify-center transition-colors ${
                      view === 'grid'
                        ? 'bg-navy text-white'
                        : 'text-text-muted hover:bg-surface'
                    }`}
                  >
                    <Grid3x3 className="h-4 w-4" />
                  </button>
                  <button
                    type="button"
                    aria-label="List view"
                    onClick={() => setView('list')}
                    className={`flex h-8 w-8 items-center justify-center border-l border-border transition-colors ${
                      view === 'list'
                        ? 'bg-navy text-white'
                        : 'text-text-muted hover:bg-surface'
                    }`}
                  >
                    <List className="h-4 w-4" />
                  </button>
                </div>

                <select
                  value={sortBy}
                  onChange={(e) => setSortBy(e.target.value)}
                  className="h-8 rounded-md border border-border bg-white px-2 text-[13px] text-text-primary outline-none focus:ring-1 focus:ring-navy"
                >
                  <option value="relevance">Sort: Relevance</option>
                  <option value="price-asc">Price ↑</option>
                  <option value="price-desc">Price ↓</option>
                  <option value="sold-desc">Most Sold</option>
                  <option value="newest">Newest</option>
                </select>
              </div>
            </div>

            {/* Product grid */}
            {view === 'grid' ? (
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                {filteredProducts.map((product) => (
                  <ProductCard
                    key={product.id}
                    product={product}
                    onInquiry={handleInquiry}
                  />
                ))}
              </div>
            ) : (
              <div className="flex flex-col gap-4">
                {filteredProducts.map((product) => (
                  <ProductCard
                    key={product.id}
                    product={product}
                    onInquiry={handleInquiry}
                  />
                ))}
              </div>
            )}

            {filteredProducts.length === 0 && (
              <div className="flex flex-col items-center py-16 text-center">
                <p className="text-[16px] font-semibold text-navy">No products found</p>
                <p className="mt-2 text-[14px] text-text-secondary">
                  Try adjusting your filters or browse a different category.
                </p>
                <button
                  type="button"
                  onClick={handleClear}
                  className="mt-4 rounded-md bg-gold px-4 py-2 text-[14px] font-semibold text-white transition-colors hover:bg-gold-hover"
                >
                  Clear all filters
                </button>
              </div>
            )}

            {/* Pagination */}
            <nav
              aria-label="Pagination"
              className="mt-8 flex items-center justify-center gap-1"
            >
              <button
                type="button"
                className="rounded-md px-3 py-1.5 text-[13px] text-text-secondary transition-colors hover:text-navy"
              >
                ← Prev
              </button>
              <button
                type="button"
                aria-current="page"
                className="flex h-9 w-9 items-center justify-center rounded-full bg-navy text-[13px] font-semibold text-white"
              >
                1
              </button>
              {[2, 3].map((page) => (
                <button
                  key={page}
                  type="button"
                  className="flex h-9 w-9 items-center justify-center rounded-md text-[13px] text-text-secondary transition-colors hover:bg-surface hover:text-navy"
                >
                  {page}
                </button>
              ))}
              <span className="px-1 text-text-muted">…</span>
              <button
                type="button"
                className="flex h-9 w-9 items-center justify-center rounded-md text-[13px] text-text-secondary transition-colors hover:bg-surface hover:text-navy"
              >
                24
              </button>
              <button
                type="button"
                className="rounded-md px-3 py-1.5 text-[13px] text-text-secondary transition-colors hover:text-navy"
              >
                Next →
              </button>
            </nav>
          </section>
        </main>
      </div>

      <Footer />

      {/* Mobile FAB */}
      <button
        type="button"
        onClick={() => setMobileFiltersOpen(true)}
        className="fixed bottom-5 right-5 z-40 flex h-12 items-center gap-2 rounded-full bg-navy px-5 text-[14px] font-semibold text-white shadow-lg transition-colors hover:bg-navy-hover lg:hidden"
      >
        <SlidersHorizontal className="h-4 w-4" />
        Filters
      </button>

      {/* Mobile filter sheet */}
      {mobileFiltersOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div
            className="absolute inset-0 bg-black/40"
            onClick={() => setMobileFiltersOpen(false)}
            aria-hidden="true"
          />
          <div className="absolute bottom-0 left-0 right-0 max-h-[85vh] overflow-y-auto rounded-t-2xl bg-white p-4 shadow-xl">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-[16px] font-semibold text-navy">Filters</h2>
              <button
                type="button"
                onClick={() => setMobileFiltersOpen(false)}
                aria-label="Close filters"
                className="flex h-8 w-8 items-center justify-center rounded-md text-text-muted transition-colors hover:bg-surface"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <FilterSidebar {...filterProps} />
          </div>
        </div>
      )}
    </div>
  );
}

export const Route = createRoute({
  getParentRoute: () => rootRoute,
  path: '/catalog',
  component: CatalogPage,
  head: () => ({
    meta: [
      {
        title:
          'Wholesale Catalog — TradeFlow Colón | CFZ Verified Suppliers',
      },
      {
        name: 'description',
        content:
          'Browse 1,342+ wholesale products from CFZ-verified manufacturers in the Colón Free Zone. Export-ready, secure payments, MOQ from 10 units.',
      },
      {
        property: 'og:title',
        content:
          'Wholesale Catalog — TradeFlow Colón | CFZ Verified Suppliers',
      },
      {
        property: 'og:description',
        content:
          'Browse 1,342+ wholesale products from CFZ-verified manufacturers in the Colón Free Zone. Export-ready, secure payments, MOQ from 10 units.',
      },
    ],
  }),
});
