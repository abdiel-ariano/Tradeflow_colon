const ABOUT_LINKS = [
  'Why TradeFlow Colón',
  'Colón Free Zone Guide',
  'Corporate responsibility',
];

const BUYER_LINKS = [
  'Secure payments',
  'Money-back guarantee',
  'Guaranteed delivery',
  'After-sales protection',
];

const SOURCE_LINKS = [
  'CFZ Verified manufacturers',
  'Request for Quotation',
  'Export documentation',
];

const HELP_LINKS = [
  'For buyers',
  'Live chat',
  'Open a dispute',
  'Refunds',
];

const PAYMENT_METHODS = [
  'Visa',
  'Mastercard',
  'PayPal',
  'Apple Pay',
  'Google Pay',
  'Bank Transfer (T/T)',
];

function LinkColumn({ title, links }: { title: string; links: string[] }) {
  return (
    <div>
      <p className="text-[14px] font-semibold text-navy">{title}</p>
      <ul className="mt-3 space-y-2">
        {links.map((link) => (
          <li key={link}>
            <a
              href="#"
              className="text-[13px] text-text-secondary transition-colors hover:text-navy-mid"
            >
              {link}
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function Footer() {
  return (
    <footer className="mt-12 border-t border-border bg-white">
      <div className="mx-auto max-w-[1440px] px-4 py-10 lg:px-6">
        <div className="grid grid-cols-2 gap-8 lg:grid-cols-4">
          <LinkColumn title="About TradeFlow" links={ABOUT_LINKS} />
          <LinkColumn title="Buyer Protection" links={BUYER_LINKS} />
          <LinkColumn title="Source from CFZ" links={SOURCE_LINKS} />
          <LinkColumn title="Help Center" links={HELP_LINKS} />
        </div>

        <div className="mt-8 flex flex-wrap items-center gap-3">
          <span className="text-[13px] font-medium text-text-secondary">We accept:</span>
          {PAYMENT_METHODS.map((method) => (
            <span
              key={method}
              className="rounded border border-border px-2.5 py-1 text-[12px] font-medium text-text-secondary"
            >
              {method}
            </span>
          ))}
        </div>
      </div>

      <div className="border-t border-border bg-surface">
        <div className="mx-auto flex max-w-[1440px] flex-col items-center justify-between gap-2 px-4 py-4 text-center sm:flex-row lg:px-6">
          <p className="text-[12px] text-text-muted">
            © 2025–2026 TradeFlow Colón · Privacy · Terms · Legal Notice
          </p>
          <p className="text-[12px] text-text-muted">
            Trade from the Colón Free Zone · Panama 🇵🇦
          </p>
        </div>
      </div>
    </footer>
  );
}
