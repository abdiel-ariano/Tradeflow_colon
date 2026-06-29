import { categories } from '@/lib/catalog-data';

interface FilterSidebarProps {
  sortBy: string;
  onSortChange: (value: string) => void;
  selectedCategories: string[];
  onCategoryToggle: (categoryId: string) => void;
  priceMin: number;
  priceMax: number;
  onPriceMinChange: (value: number) => void;
  onPriceMaxChange: (value: number) => void;
  trustLevels: string[];
  onTrustToggle: (level: string) => void;
  minOrder: string;
  onMinOrderChange: (value: string) => void;
  supplierTenure: string;
  onSupplierTenureChange: (value: string) => void;
  onApply: () => void;
  onClear: () => void;
}

const sortOptions = [
  { value: 'relevance', label: 'Relevance' },
  { value: 'price-asc', label: 'Price: Low to High' },
  { value: 'price-desc', label: 'Price: High to Low' },
  { value: 'moq-asc', label: 'MOQ: Low to High' },
  { value: 'sold-desc', label: 'Best Selling' },
];

const trustOptions = [
  { value: 'cfz-verified', label: 'CFZ Verified' },
  { value: 'export-ready', label: 'Export-Ready' },
  { value: 'top-rated', label: 'Top Rated Suppliers' },
];

const minOrderOptions = [
  { value: 'any', label: 'Any quantity' },
  { value: '10', label: '10+ pieces' },
  { value: '50', label: '50+ pieces' },
  { value: '100', label: '100+ pieces' },
  { value: '500', label: '500+ pieces' },
];

const tenureOptions = [
  { value: 'any', label: 'Any tenure' },
  { value: '3', label: '3+ years' },
  { value: '5', label: '5+ years' },
  { value: '10', label: '10+ years' },
];

function FilterSection({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="border-b border-border py-4">
      <h3 className="mb-3 text-[16px] font-semibold text-navy">{title}</h3>
      {children}
    </div>
  );
}

export function FilterSidebar({
  sortBy,
  onSortChange,
  selectedCategories,
  onCategoryToggle,
  priceMin,
  priceMax,
  onPriceMinChange,
  onPriceMaxChange,
  trustLevels,
  onTrustToggle,
  minOrder,
  onMinOrderChange,
  supplierTenure,
  onSupplierTenureChange,
  onApply,
  onClear,
}: FilterSidebarProps) {
  return (
    <aside className="w-full">
      <FilterSection title="Sort by">
        <select
          value={sortBy}
          onChange={(e) => onSortChange(e.target.value)}
          className="h-10 w-full rounded-[4px] border border-border bg-white px-3 text-[14px] text-text-primary outline-none focus:border-navy"
        >
          {sortOptions.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </FilterSection>

      <FilterSection title="Categories">
        <ul className="space-y-2">
          {categories.map((cat) => (
            <li key={cat.id}>
              <label className="flex cursor-pointer items-center justify-between text-[13px]">
                <span className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={selectedCategories.includes(cat.id)}
                    onChange={() => onCategoryToggle(cat.id)}
                    className="h-4 w-4 rounded-[4px] border-border accent-navy"
                  />
                  <span className="text-text-secondary">{cat.name}</span>
                </span>
                <span className="text-text-muted">({cat.count})</span>
              </label>
            </li>
          ))}
        </ul>
      </FilterSection>

      <FilterSection title="Price range">
        <div className="mb-3 flex gap-2">
          <input
            type="number"
            value={priceMin}
            onChange={(e) => onPriceMinChange(Number(e.target.value))}
            placeholder="Min"
            className="h-10 w-full rounded-[4px] border border-border px-3 text-[14px] outline-none focus:border-navy"
          />
          <input
            type="number"
            value={priceMax}
            onChange={(e) => onPriceMaxChange(Number(e.target.value))}
            placeholder="Max"
            className="h-10 w-full rounded-[4px] border border-border px-3 text-[14px] outline-none focus:border-navy"
          />
        </div>
        <input
          type="range"
          min={0}
          max={100}
          value={priceMax}
          onChange={(e) => onPriceMaxChange(Number(e.target.value))}
          className="w-full"
        />
      </FilterSection>

      <FilterSection title="Trust level">
        <ul className="space-y-2">
          {trustOptions.map((opt) => (
            <li key={opt.value}>
              <label className="flex cursor-pointer items-center gap-2 text-[13px]">
                <input
                  type="checkbox"
                  checked={trustLevels.includes(opt.value)}
                  onChange={() => onTrustToggle(opt.value)}
                  className="h-4 w-4 rounded-[4px] border-border accent-emerald"
                />
                <span className="text-text-secondary">{opt.label}</span>
              </label>
            </li>
          ))}
        </ul>
      </FilterSection>

      <FilterSection title="Minimum order">
        <ul className="space-y-2">
          {minOrderOptions.map((opt) => (
            <li key={opt.value}>
              <label className="flex cursor-pointer items-center gap-2 text-[13px]">
                <input
                  type="radio"
                  name="minOrder"
                  value={opt.value}
                  checked={minOrder === opt.value}
                  onChange={() => onMinOrderChange(opt.value)}
                  className="h-4 w-4 border-border accent-navy"
                />
                <span className="text-text-secondary">{opt.label}</span>
              </label>
            </li>
          ))}
        </ul>
      </FilterSection>

      <FilterSection title="Supplier tenure">
        <ul className="space-y-2">
          {tenureOptions.map((opt) => (
            <li key={opt.value}>
              <label className="flex cursor-pointer items-center gap-2 text-[13px]">
                <input
                  type="radio"
                  name="supplierTenure"
                  value={opt.value}
                  checked={supplierTenure === opt.value}
                  onChange={() => onSupplierTenureChange(opt.value)}
                  className="h-4 w-4 border-border accent-navy"
                />
                <span className="text-text-secondary">{opt.label}</span>
              </label>
            </li>
          ))}
        </ul>
      </FilterSection>

      <div className="flex flex-col gap-3 pt-4">
        <button
          type="button"
          onClick={onApply}
          className="h-10 w-full rounded-[4px] bg-navy text-[14px] font-semibold text-white transition-colors hover:bg-navy-hover"
        >
          Apply filters
        </button>
        <button
          type="button"
          onClick={onClear}
          className="text-center text-[13px] font-medium text-navy-mid transition-colors hover:text-navy"
        >
          Clear all
        </button>
      </div>
    </aside>
  );
}
