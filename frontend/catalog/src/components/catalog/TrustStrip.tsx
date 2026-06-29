import { Award, FileText, Zap } from 'lucide-react';

const items = [
  { icon: FileText, label: 'Request for Quotation' },
  { icon: Award, label: 'CFZ Top Ranked Suppliers' },
  { icon: Zap, label: 'Export-Ready Documentation' },
];

export function TrustStrip() {
  return (
    <div className="h-12 border-y border-border bg-surface">
      <div className="mx-auto flex h-full max-w-[1440px] items-center justify-center px-4 lg:px-6">
        <div className="grid w-full max-w-3xl grid-cols-3 gap-4">
          {items.map(({ icon: Icon, label }) => (
            <div key={label} className="flex items-center justify-center gap-2">
              <Icon className="h-4 w-4 shrink-0 text-navy" strokeWidth={2} />
              <span className="text-[12px] font-medium text-text-secondary sm:text-[13px]">
                {label}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
