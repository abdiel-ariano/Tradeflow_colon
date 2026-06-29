import { categories } from '@/lib/catalog-data';

interface CategoryStripProps {
  activeCategory: string | null;
  onCategoryChange: (categoryId: string | null) => void;
}

export function CategoryStrip({ activeCategory, onCategoryChange }: CategoryStripProps) {
  const displayCategories = categories.slice(0, 6);

  return (
    <nav
      aria-label="Product categories"
      className="h-12 border-b border-border bg-white"
    >
      <div className="mx-auto flex h-full max-w-[1440px] items-center px-4 lg:px-6">
        <div className="flex h-full items-center gap-2 overflow-x-auto scrollbar-none">
          <button
            type="button"
            onClick={() => onCategoryChange(null)}
            className={`shrink-0 rounded-[6px] px-4 py-1.5 text-[13px] font-medium transition-colors ${
              activeCategory === null
                ? 'bg-navy text-white'
                : 'bg-surface text-text-secondary hover:text-navy'
            }`}
          >
            All Products
          </button>
          {displayCategories.map((cat) => (
            <button
              key={cat.id}
              type="button"
              onClick={() => onCategoryChange(cat.id)}
              className={`shrink-0 rounded-[6px] px-4 py-1.5 text-[13px] font-medium transition-colors ${
                activeCategory === cat.id
                  ? 'bg-navy text-white'
                  : 'bg-surface text-text-secondary hover:text-navy'
              }`}
            >
              {cat.name}
            </button>
          ))}
        </div>
      </div>
    </nav>
  );
}
