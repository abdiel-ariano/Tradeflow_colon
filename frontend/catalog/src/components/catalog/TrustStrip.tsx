import { BadgeCheck, CreditCard, Globe, ShieldCheck } from 'lucide-react';

const trustItems = [
  { icon: BadgeCheck, label: 'CFZ Verified' },
  { icon: Globe, label: 'Export-Ready' },
  { icon: CreditCard, label: 'Secure Payments' },
  { icon: ShieldCheck, label: 'Verified Suppliers' },
];

export function TrustStrip() {
  return (
    <div className="border-b border-border bg-surface">
      <div className="mx-auto flex max-w-[1440px] flex-wrap items-center justify-center gap-6 px-4 py-3 lg:gap-10 lg:px-6">
        {trustItems.map(({ icon: Icon, label }) => (
          <div key={label} className="flex items-center gap-2">
            <Icon className="h-4 w-4 text-navy" strokeWidth={2} />
            <span className="text-[13px] font-medium text-text-secondary">{label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
