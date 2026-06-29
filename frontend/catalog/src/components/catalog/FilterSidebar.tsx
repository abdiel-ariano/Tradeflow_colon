import { useState, type ReactNode } from 'react';
import { Check, ChevronDown } from 'lucide-react';
import { ALL_CATEGORIES } from '@/lib/catalog-data';

interface FilterSidebarProps {
  activeCategory: string | null;
  onCategorySelect: (id: string) => void;
  sortBy: string;
  onSortChange: (value: string) => void;
  priceMin: number;
  priceMax: number;
  onPriceMinChange: (value: number) => void;
  onPriceMaxChange: (value: number) => void;
  trustLevels: Record<string, boolean>;
  onTrustToggle: (key: string) => void;
  minOrder: string;
  onMinOrderChange: (value: string) => void;
  supplierTenure: string;
  onSupplierTenureChange: (value: string) => void;
  onApply: () => void;
  onClear: () => void;
}

const SORT_OPTIONS = [
  { value: 'relevance', label: 'Relevance' },
  { value: 'price-asc', label: 'Price ↑' },
  { value: 'price-desc', label: 'Price ↓' },
  { value: 'sold-desc', label: 'Most Sold' },
  { value: 'newest', label: 'Newest' },
];

const TRUST_OPTIONS = [
  { key: 'cfz-verified', label: 'CFZ Verified companies only' },
  { key: 'export-docs', label: 'Has export documentation' },
  { key: 'international', label: 'Accepts international orders' },
];

const MIN_ORDER_OPTIONS = [
  { value: 'any', label: 'Any' },
  { value: 'lt50', label: '<50' },
  { value: '50-200', label: '50–200' },
  { value: '200+', label: '200+' },
];

const TENURE_OPTIONS = [
  { value: 'any', label: 'Any' },
  { value: '1', label: '1+ years' },
  { value: '3', label: '3+ years' },
  { value: '5', label: '5+ years' },
];

function FilterSection({
  title,
  defaultOpen = true,
  children,
}: {
  title: string;
  defaultOpen?: boolean;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className="border-b border-border py-4">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="mb-3 flex w-full items-center justify-between text-[16px] font-semibold text-navy"
      >
        {title}
        <ChevronDown
          className={`h-4 w-4 text-text-muted transition-transform duration-150 ${open ? 'rotate-180' : ''}`}
        />
      </button>
      {open && children}
    </div>
  );
}

export function FilterSidebar({
  activeCategory,
  onCategorySelect,
  sortBy,
  onSortChange,
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
    <aside className="w-60">
      <FilterSection title="Sort by">
        <select
          value={sortBy}
          onChange={(e) => onSortChange(e.target.value)}
          className="h-10 w-full rounded-md border border-border bg-white px-3 text-[14px] text-text-primary outline-none focus:ring-1 focus:ring-navy"
        >
          {SORT_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </FilterSection>

      <FilterSection title="Categories">
        <ul className="space-y-2">
          {ALL_CATEGORIES.map((cat) => {
            const isActive = activeCategory === cat.id;
            return (
              <li key={cat.id}>
                <button
                  type="button"
                  onClick={() => onCategorySelect(cat.id)}
                  className={`flex w-full items-center justify-between text-[13px] transition-colors ${
                    isActive
                      ? 'font-semibold text-navy'
                      : 'text-text-secondary hover:text-navy'
                  }`}
                >
                  <span>
                    {cat.icon} {cat.label}
                  </span>
                  <span className="text-text-secondary">({cat.count})</span>
                </button>
              </li>
            );
          })}
        </ul>
      </FilterSection>

      <FilterSection title="Price range">
        <div className="mb-3 flex gap-2">
          <input
            type="number"
            value={priceMin || ''}
            onChange={(e) => onPriceMinChange(Number(e.target.value))}
            placeholder="Min PAB"
            className="h-10 w-full rounded-md border border-border px-3 text-[14px] outline-none focus:ring-1 focus:ring-navy"
          />
          <input
            type="number"
            value={priceMax < 500 ? priceMax : ''}
            onChange={(e) => onPriceMaxChange(Number(e.target.value))}
            placeholder="Max PAB"
            className="h-10 w-full rounded-md border border-border px-3 text-[14px] outline-none focus:ring-1 focus:ring-navy"
          />
        </div>
        <input
          type="range"
          min={0}
          max={500}
          value={priceMax}
          onChange={(e) => onPriceMaxChange(Number(e.target.value))}
          className="w-full"
        />
      </FilterSection>

      <FilterSection title="Trust level">
        <ul className="space-y-2">
          {TRUST_OPTIONS.map((opt) => {
            const checked = trustLevels[opt.key] ?? false;
            return (
              <li key={opt.key}>
                <label className="flex cursor-pointer items-center gap-2.5 text-[13px]">
                  <span
                    className={`flex h-4 w-4 shrink-0 items-center justify-center rounded border transition-colors ${
                      checked
                        ? 'border-emerald bg-emerald'
                        : 'border-border bg-white'
                    }`}
                  >
                    {checked && <Check className="h-3 w-3 text-white" strokeWidth={3} />}
                  </span>
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => onTrustToggle(opt.key)}
                    className="sr-only"
                  />
                  <span className="text-text-secondary">{opt.label}</span>
                </label>
              </li>
            );
          })}
        </ul>
      </FilterSection>

      <FilterSection title="Minimum order">
        <ul className="space-y-2">
          {MIN_ORDER_OPTIONS.map((opt) => (
            <li key={opt.value}>
              <label className="flex cursor-pointer items-center gap-2 text-[13px]">
                <input
                  type="radio"
                  name="minOrder"
                  value={opt.value}
                  checked={minOrder === opt.value}
                  onChange={() => onMinOrderChange(opt.value)}
                  className="h-4 w-4 accent-navy"
                />
                <span className="text-text-secondary">{opt.label}</span>
              </label>
            </li>
          ))}
        </ul>
      </FilterSection>

      <FilterSection title="Supplier tenure">
        <ul className="space-y-2">
          {TENURE_OPTIONS.map((opt) => (
            <li key={opt.value}>
              <label className="flex cursor-pointer items-center gap-2 text-[13px]">
                <input
                  type="radio"
                  name="supplierTenure"
                  value={opt.value}
                  checked={supplierTenure === opt.value}
                  onChange={() => onSupplierTenureChange(opt.value)}
                  className="h-4 w-4 accent-navy"
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
          className="h-10 w-full rounded-md bg-navy text-[14px] font-semibold text-white transition-colors hover:bg-navy-hover"
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
