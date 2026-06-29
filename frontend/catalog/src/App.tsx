import { useCallback, useMemo, useState } from 'react';
import { Grid3X3, List, SlidersHorizontal, X } from 'lucide-react';
import { CategoryStrip } from '@/components/catalog/CategoryStrip';
import { FilterSidebar } from '@/components/catalog/FilterSidebar';
import { Footer } from '@/components/catalog/Footer';
import { Navbar } from '@/components/catalog/Navbar';
import { ProductCard } from '@/components/catalog/ProductCard';
import { TrustStrip } from '@/components/catalog/TrustStrip';
import { products, type Product } from '@/lib/catalog-data';

type ViewMode = 'grid' | 'list';

function filterProducts(
  items: Product[],
  activeCategory: string | null,
  selectedCategories: string[],
  priceMin: number,
  priceMax: number,
  trustLevels: string[],
  minOrder: string,
  supplierTenure: string,
  sortBy: string,
): Product[] {
  let result = [...items];

  if (activeCategory) {
    result = result.filter((p) => p.category === activeCategory);
  }

  if (selectedCategories.length > 0) {
    result = result.filter((p) => selectedCategories.includes(p.category));
  }

  if (priceMin > 0) {
    result = result.filter((p) => p.priceMin >= priceMin);
  }
  if (priceMax < 100) {
    result = result.filter((p) => p.priceMax <= priceMax);
  }

  if (trustLevels.includes('cfz-verified')) {
    result = result.filter((p) => p.verified);
  }

  if (minOrder !== 'any') {
    const threshold = Number(minOrder);
    result = result.filter((p) => p.moq >= threshold);
  }

  if (supplierTenure !== 'any') {
    const threshold = Number(supplierTenure);
    result = result.filter((p) => p.years >= threshold);
  }

  switch (sortBy) {
    case 'price-asc':
      result.sort((a, b) => a.priceMin - b.priceMin);
      break;
    case 'price-desc':
      result.sort((a, b) => b.priceMax - a.priceMax);
      break;
    case 'moq-asc':
      result.sort((a, b) => a.moq - b.moq);
      break;
    case 'sold-desc':
      result.sort((a, b) => b.sold - a.sold);
      break;
  }

  return result;
}

export default function App() {
  const [activeCategory, setActiveCategory] = useState<string | null>(null);
  const [view, setView] = useState<ViewMode>('grid');
  const [inquiryCount, setInquiryCount] = useState(0);
  const [mobileFiltersOpen, setMobileFiltersOpen] = useState(false);

  const [sortBy, setSortBy] = useState('relevance');
  const [selectedCategories, setSelectedCategories] = useState<string[]>([]);
  const [priceMin, setPriceMin] = useState(0);
  const [priceMax, setPriceMax] = useState(100);
  const [trustLevels, setTrustLevels] = useState<string[]>([]);
  const [minOrder, setMinOrder] = useState('any');
  const [supplierTenure, setSupplierTenure] = useState('any');

  const filteredProducts = useMemo(
    () =>
      filterProducts(
        products,
        activeCategory,
        selectedCategories,
        priceMin,
        priceMax,
        trustLevels,
        minOrder,
        supplierTenure,
        sortBy,
      ),
    [activeCategory, selectedCategories, priceMin, priceMax, trustLevels, minOrder, supplierTenure, sortBy],
  );

  const handleAddToInquiry = useCallback(() => {
    setInquiryCount((c) => c + 1);
  }, []);

  const handleCategoryToggle = useCallback((categoryId: string) => {
    setSelectedCategories((prev) =>
      prev.includes(categoryId)
        ? prev.filter((id) => id !== categoryId)
        : [...prev, categoryId],
    );
  }, []);

  const handleTrustToggle = useCallback((level: string) => {
    setTrustLevels((prev) =>
      prev.includes(level) ? prev.filter((l) => l !== level) : [...prev, level],
    );
  }, []);

  const handleClearFilters = useCallback(() => {
    setSortBy('relevance');
    setSelectedCategories([]);
    setPriceMin(0);
    setPriceMax(100);
    setTrustLevels([]);
    setMinOrder('any');
    setSupplierTenure('any');
    setActiveCategory(null);
  }, []);

  const filterSidebarProps = {
    sortBy,
    onSortChange: setSortBy,
    selectedCategories,
    onCategoryToggle: handleCategoryToggle,
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
    onClear: handleClearFilters,
  };

  return (
    <div className="min-h-screen bg-white">
      <Navbar inquiryCount={inquiryCount} />
      <CategoryStrip
        activeCategory={activeCategory}
        onCategoryChange={setActiveCategory}
      />
      <TrustStrip />

      <main className="mx-auto max-w-[1440px] px-4 py-6 lg:px-6">
        <div className="mb-4 flex items-center justify-between">
          <p className="text-[14px] text-text-secondary">
            <span className="font-semibold text-navy">{filteredProducts.length}</span>{' '}
            products found
          </p>

          <div className="flex items-center gap-1">
            <button
              type="button"
              aria-label="Grid view"
              onClick={() => setView('grid')}
              className={`flex h-8 w-8 items-center justify-center rounded-[4px] transition-colors ${
                view === 'grid'
                  ? 'bg-navy text-white'
                  : 'text-text-muted hover:bg-surface'
              }`}
            >
              <Grid3X3 className="h-4 w-4" />
            </button>
            <button
              type="button"
              aria-label="List view"
              onClick={() => setView('list')}
              className={`flex h-8 w-8 items-center justify-center rounded-[4px] transition-colors ${
                view === 'list'
                  ? 'bg-navy text-white'
                  : 'text-text-muted hover:bg-surface'
              }`}
            >
              <List className="h-4 w-4" />
            </button>
          </div>
        </div>

        <div className="flex gap-6">
          <div className="hidden w-[240px] shrink-0 lg:block">
            <div className="sticky top-[120px]">
              <FilterSidebar {...filterSidebarProps} />
            </div>
          </div>

          <div className="flex-1">
            {view === 'grid' ? (
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                {filteredProducts.map((product) => (
                  <ProductCard
                    key={product.id}
                    product={product}
                    onAddToInquiry={handleAddToInquiry}
                  />
                ))}
              </div>
            ) : (
              <div className="flex flex-col gap-4">
                {filteredProducts.map((product) => (
                  <ProductCard
                    key={product.id}
                    product={product}
                    onAddToInquiry={handleAddToInquiry}
                  />
                ))}
              </div>
            )}

            {filteredProducts.length === 0 && (
              <div className="flex flex-col items-center justify-center py-16 text-center">
                <p className="text-[16px] font-semibold text-navy">No products found</p>
                <p className="mt-2 text-[14px] text-text-secondary">
                  Try adjusting your filters or browse a different category.
                </p>
                <button
                  type="button"
                  onClick={handleClearFilters}
                  className="mt-4 rounded-[4px] bg-orange px-4 py-2 text-[14px] font-semibold text-white transition-colors hover:bg-orange-hover"
                >
                  Clear all filters
                </button>
              </div>
            )}
          </div>
        </div>
      </main>

      <Footer />

      {/* Mobile filter FAB */}
      <button
        type="button"
        onClick={() => setMobileFiltersOpen(true)}
        className="fixed bottom-6 right-6 z-40 flex h-12 items-center gap-2 rounded-full bg-orange px-5 text-[14px] font-semibold text-white shadow-lg transition-colors hover:bg-orange-hover lg:hidden"
      >
        <SlidersHorizontal className="h-4 w-4" />
        Filters
      </button>

      {/* Mobile filter bottom sheet */}
      {mobileFiltersOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div
            className="absolute inset-0 bg-navy/40"
            onClick={() => setMobileFiltersOpen(false)}
            aria-hidden="true"
          />
          <div className="absolute bottom-0 left-0 right-0 max-h-[85vh] overflow-y-auto rounded-t-[6px] bg-white p-4 shadow-xl">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-[16px] font-semibold text-navy">Filters</h2>
              <button
                type="button"
                onClick={() => setMobileFiltersOpen(false)}
                aria-label="Close filters"
                className="flex h-8 w-8 items-center justify-center rounded-[4px] text-text-muted hover:bg-surface"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <FilterSidebar {...filterSidebarProps} />
          </div>
        </div>
      )}
    </div>
  );
}
