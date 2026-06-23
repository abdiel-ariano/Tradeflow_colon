import * as React from 'react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';

export type DataTableColumn<T> = {
  key: string;
  label: string;
  width?: string;
  render?: (value: unknown, row: T) => React.ReactNode;
};

export type DataTableProps<T extends Record<string, unknown>> = {
  columns: DataTableColumn<T>[];
  rows?: T[];
  loading?: boolean;
  emptyMessage?: string;
  onView?: (row: T) => void;
  className?: string;
};

export function DataTable<T extends Record<string, unknown>>({
  columns,
  rows = [],
  loading = false,
  emptyMessage = 'No records found.',
  onView,
  className,
}: DataTableProps<T>) {
  return (
    <div className={cn('overflow-x-auto', className)}>
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr>
            {columns.map((col) => (
              <th
                key={col.key}
                className="border-b border-gray-border px-4 py-3 text-left text-label uppercase tracking-widest text-gray-mid"
                style={col.width ? { width: col.width } : undefined}
              >
                {col.label}
              </th>
            ))}
            {onView ? <th className="border-b border-gray-border px-4 py-3" /> : null}
          </tr>
        </thead>
        <tbody>
          {loading
            ? [0, 1, 2].map((i) => (
                <tr key={i}>
                  <td colSpan={columns.length + (onView ? 1 : 0)} className="px-4 py-4">
                    <div className="h-3.5 animate-pulse rounded bg-gray-border" />
                  </td>
                </tr>
              ))
            : null}
          {!loading && rows.length === 0 ? (
            <tr>
              <td
                colSpan={columns.length + (onView ? 1 : 0)}
                className="px-4 py-12 text-center text-gray-mid"
              >
                {emptyMessage}
              </td>
            </tr>
          ) : null}
          {!loading
            ? rows.map((row, idx) => (
                <tr key={idx} className="hover:bg-gray-page/80">
                  {columns.map((col) => (
                    <td key={col.key} className="border-b border-gray-border px-4 py-3.5 text-gray-text">
                      {col.render ? col.render(row[col.key], row) : String(row[col.key] ?? '')}
                    </td>
                  ))}
                  {onView ? (
                    <td className="border-b border-gray-border px-4 py-3.5 text-right">
                      <Button variant="outline" size="sm" onClick={() => onView(row)}>
                        View
                      </Button>
                    </td>
                  ) : null}
                </tr>
              ))
            : null}
        </tbody>
      </table>
    </div>
  );
}
