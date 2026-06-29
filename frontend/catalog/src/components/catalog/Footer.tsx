export function Footer() {
  return (
    <footer className="mt-12 border-t border-border bg-surface">
      <div className="mx-auto max-w-[1440px] px-4 py-8 lg:px-6">
        <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <p className="text-[16px] font-semibold text-navy">TradeFlow Colón</p>
            <p className="mt-2 text-[13px] leading-relaxed text-text-secondary">
              The wholesale marketplace of the Colón Free Zone. Connect with CFZ-verified
              suppliers and request quotes on export-ready inventory.
            </p>
          </div>

          <div>
            <p className="text-[14px] font-semibold text-navy">For Buyers</p>
            <ul className="mt-3 space-y-2 text-[13px] text-text-secondary">
              <li>
                <a href="#" className="transition-colors hover:text-navy-mid">
                  Browse catalog
                </a>
              </li>
              <li>
                <a href="#" className="transition-colors hover:text-navy-mid">
                  Request a quote
                </a>
              </li>
              <li>
                <a href="#" className="transition-colors hover:text-navy-mid">
                  Verified suppliers
                </a>
              </li>
            </ul>
          </div>

          <div>
            <p className="text-[14px] font-semibold text-navy">For Suppliers</p>
            <ul className="mt-3 space-y-2 text-[13px] text-text-secondary">
              <li>
                <a href="#" className="transition-colors hover:text-navy-mid">
                  List your products
                </a>
              </li>
              <li>
                <a href="#" className="transition-colors hover:text-navy-mid">
                  CFZ verification
                </a>
              </li>
              <li>
                <a href="#" className="transition-colors hover:text-navy-mid">
                  Seller dashboard
                </a>
              </li>
            </ul>
          </div>

          <div>
            <p className="text-[14px] font-semibold text-navy">Contact</p>
            <ul className="mt-3 space-y-2 text-[13px] text-text-secondary">
              <li>Colón Free Zone, Panama</li>
              <li>
                <a
                  href="mailto:info@tradeflowcolon.com"
                  className="transition-colors hover:text-navy-mid"
                >
                  info@tradeflowcolon.com
                </a>
              </li>
            </ul>
          </div>
        </div>

        <div className="mt-8 border-t border-border pt-6 text-center text-[12px] text-text-muted">
          © {new Date().getFullYear()} TradeFlow Colón · Colón Free Zone, Panama
        </div>
      </div>
    </footer>
  );
}
