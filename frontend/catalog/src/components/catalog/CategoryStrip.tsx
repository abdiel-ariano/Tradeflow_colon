import { CATEGORIES } from '@/lib/catalog-data';

interface CategoryStripProps {
  activeCategory: string | null;
  onChange: (id: string | null) => void;
}

export function CategoryStrip({ activeCategory, onChange }: CategoryStripProps) {
  return (
    <nav
      aria-label="Product categories"
      className="h-12 border-b border-border bg-white"
    >
      <div className="mx-auto flex h-full max-w-[1440px] items-center px-4 lg:px-6">
        <div className="no-scrollbar flex h-full items-center gap-2 overflow-x-auto">
          <button
            type="button"
            onClick={() => onChange(null)}
            className={`flex h-9 shrink-0 items-center gap-1.5 rounded-full border px-4 text-[13px] font-medium transition-colors ${
              activeCategory === null
                ? 'border-navy bg-navy text-white'
                : 'border-border text-text-secondary hover:border-navy'
            }`}
          >
            All
          </button>
          {CATEGORIES.map((cat) => (
            <button
              key={cat.id}
              type="button"
              onClick={() => onChange(cat.id)}
              className={`flex h-9 shrink-0 items-center gap-1.5 rounded-full border px-4 text-[13px] font-medium transition-colors ${
                activeCategory === cat.id
                  ? 'border-navy bg-navy text-white'
                  : 'border-border text-text-secondary hover:border-navy'
              }`}
            >
              <span aria-hidden="true">{cat.icon}</span>
              {cat.label}
              <span className={activeCategory === cat.id ? 'text-white/80' : 'text-text-muted'}>
                ({cat.count})
              </span>
            </button>
          ))}
        </div>
      </div>
    </nav>
  );
}
