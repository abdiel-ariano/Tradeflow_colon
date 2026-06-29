export type Product = {
  id: string;
  name: string;
  emoji: string;
  bg: string;
  priceMin: number;
  priceMax?: number;
  originalPrice?: number;
  discount?: number;
  moq: number;
  moqUnit: string;
  sold: number;
  years: number;
  country: string;
  flag: string;
  verified: boolean;
  reorderRate?: number;
  lowerPriced?: boolean;
};

export const CATEGORIES = [
  { id: 'electronics', icon: '📱', label: 'Electronics & Office', count: 314 },
  { id: 'textiles', icon: '👕', label: 'Textiles & Uniforms', count: 254 },
  { id: 'imports', icon: '📦', label: 'General Imports', count: 235 },
  { id: 'logistics', icon: '🚚', label: 'Logistics & Packaging', count: 146 },
  { id: 'home', icon: '🏠', label: 'Home & Appliances', count: 139 },
  { id: 'accessories', icon: '👜', label: 'Accessories & Leather', count: 138 },
];

export const ALL_CATEGORIES = [
  ...CATEGORIES,
  { id: 'automotive', icon: '🚗', label: 'Automotive Parts', count: 98 },
  { id: 'beauty', icon: '💄', label: 'Beauty & Personal Care', count: 87 },
  { id: 'industrial', icon: '🏭', label: 'Industrial Equipment', count: 76 },
  { id: 'food', icon: '🥫', label: 'Food & Beverage', count: 54 },
];

export const PRODUCTS: (Product & { category: string })[] = [
  {
    id: '1',
    name: 'Wireless Bluetooth Earbuds Pro — Bulk OEM Packaging',
    emoji: '🎧',
    bg: '#E8F0FE',
    priceMin: 8.5,
    priceMax: 12.9,
    originalPrice: 10.6,
    discount: 20,
    moq: 100,
    moqUnit: 'pieces',
    sold: 3270,
    years: 7,
    country: 'Panama',
    flag: '🇵🇦',
    verified: true,
    reorderRate: 94,
    lowerPriced: true,
    category: 'electronics',
  },
  {
    id: '2',
    name: 'Industrial Safety Work Uniform Set — High Visibility',
    emoji: '👷',
    bg: '#FFF3E0',
    priceMin: 14.2,
    priceMax: 18.5,
    moq: 50,
    moqUnit: 'sets',
    sold: 1840,
    years: 12,
    country: 'Colombia',
    flag: '🇨🇴',
    verified: true,
    reorderRate: 88,
    lowerPriced: false,
    category: 'textiles',
  },
  {
    id: '3',
    name: 'Stainless Steel Water Bottle 750ml — Custom Logo',
    emoji: '🍶',
    bg: '#E8F5E9',
    priceMin: 3.8,
    priceMax: 5.2,
    originalPrice: 4.75,
    discount: 20,
    moq: 200,
    moqUnit: 'pieces',
    sold: 5620,
    years: 5,
    country: 'China',
    flag: '🇨🇳',
    verified: true,
    reorderRate: 91,
    lowerPriced: true,
    category: 'general',
  },
  {
    id: '4',
    name: 'Corrugated Shipping Boxes — Export Grade 40×30×25cm',
    emoji: '📦',
    bg: '#F5F0E8',
    priceMin: 0.85,
    priceMax: 1.4,
    moq: 500,
    moqUnit: 'units',
    sold: 12400,
    years: 9,
    country: 'Panama',
    flag: '🇵🇦',
    verified: true,
    reorderRate: 96,
    lowerPriced: false,
    category: 'logistics',
  },
  {
    id: '5',
    name: 'Commercial Blender 2L — 1500W Heavy Duty',
    emoji: '🫕',
    bg: '#FCE4EC',
    priceMin: 42.5,
    priceMax: 58.0,
    originalPrice: 53.1,
    discount: 20,
    moq: 20,
    moqUnit: 'units',
    sold: 890,
    years: 6,
    country: 'Mexico',
    flag: '🇲🇽',
    verified: true,
    reorderRate: 82,
    lowerPriced: true,
    category: 'home',
  },
  {
    id: '6',
    name: 'Genuine Leather Belt Collection — Wholesale Lot',
    emoji: '👔',
    bg: '#EFEBE9',
    priceMin: 6.5,
    priceMax: 9.8,
    moq: 100,
    moqUnit: 'pieces',
    sold: 2150,
    years: 8,
    country: 'Italy',
    flag: '🇮🇹',
    verified: true,
    reorderRate: 79,
    lowerPriced: false,
    category: 'accessories',
  },
  {
    id: '7',
    name: 'USB-C Hub 7-in-1 — Aluminum Alloy Docking Station',
    emoji: '🔌',
    bg: '#E3F2FD',
    priceMin: 11.2,
    priceMax: 15.6,
    moq: 50,
    moqUnit: 'pieces',
    sold: 4520,
    years: 4,
    country: 'Taiwan',
    flag: '🇹🇼',
    verified: true,
    reorderRate: 93,
    lowerPriced: true,
    category: 'electronics',
  },
  {
    id: '8',
    name: 'Organic Coffee Beans 1kg — Arabica Single Origin',
    emoji: '☕',
    bg: '#FFF8E1',
    priceMin: 9.8,
    priceMax: 14.5,
    originalPrice: 12.25,
    discount: 20,
    moq: 40,
    moqUnit: 'bags',
    sold: 1680,
    years: 10,
    country: 'Costa Rica',
    flag: '🇨🇷',
    verified: true,
    reorderRate: 87,
    lowerPriced: false,
    category: 'food',
  },
  {
    id: '9',
    name: 'LED Desk Lamp with Wireless Charger — Touch Control',
    emoji: '💡',
    bg: '#E0F7FA',
    priceMin: 18.9,
    priceMax: 24.5,
    moq: 30,
    moqUnit: 'units',
    sold: 2340,
    years: 5,
    country: 'South Korea',
    flag: '🇰🇷',
    verified: true,
    reorderRate: 85,
    lowerPriced: true,
    category: 'electronics',
  },
  {
    id: '10',
    name: 'Medical Grade Face Masks — ASTM Level 3 (Box of 50)',
    emoji: '😷',
    bg: '#E8F4F0',
    priceMin: 4.2,
    priceMax: 6.8,
    moq: 100,
    moqUnit: 'boxes',
    sold: 8900,
    years: 3,
    country: 'USA',
    flag: '🇺🇸',
    verified: true,
    reorderRate: 90,
    lowerPriced: false,
    category: 'health',
  },
  {
    id: '11',
    name: 'Power Drill Set 20V — Cordless with 2 Batteries',
    emoji: '🔧',
    bg: '#FBE9E7',
    priceMin: 35.0,
    priceMax: 48.5,
    originalPrice: 43.75,
    discount: 20,
    moq: 15,
    moqUnit: 'sets',
    sold: 1120,
    years: 7,
    country: 'Germany',
    flag: '🇩🇪',
    verified: true,
    reorderRate: 84,
    lowerPriced: true,
    category: 'construction',
  },
  {
    id: '12',
    name: 'Car Phone Mount Magnetic — Dashboard & Vent Clip',
    emoji: '🚗',
    bg: '#ECEFF1',
    priceMin: 2.1,
    priceMax: 3.5,
    moq: 300,
    moqUnit: 'pieces',
    sold: 6780,
    years: 6,
    country: 'China',
    flag: '🇨🇳',
    verified: true,
    reorderRate: 92,
    lowerPriced: true,
    category: 'automotive',
  },
];

const COUNTRY_CODES: Record<string, string> = {
  Panama: 'PA',
  Colombia: 'CO',
  China: 'CN',
  Mexico: 'MX',
  Italy: 'IT',
  Taiwan: 'TW',
  'Costa Rica': 'CR',
  'South Korea': 'KR',
  USA: 'US',
  Germany: 'DE',
};

export function countryCode(country: string): string {
  return COUNTRY_CODES[country] ?? country.slice(0, 2).toUpperCase();
}

export function formatPrice(min: number, max?: number): string {
  const fmt = (n: number) =>
    n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  if (max !== undefined) {
    return `PAB ${fmt(min)}–${fmt(max)}`;
  }
  return `PAB ${fmt(min)}`;
}

export function formatSold(n: number): string {
  return n.toLocaleString('en-US') + ' sold';
}

export function categoryLabel(id: string): string {
  return ALL_CATEGORIES.find((c) => c.id === id)?.label ?? id;
}
