import { useState } from "react";
import { ChevronUp, ChevronDown, ChevronsUpDown } from "lucide-react";

export type SortDir = "asc" | "desc";

/** Lightweight client-side sorting for small tables. */
export function useSort<T>(
  rows: T[],
  accessors: Record<string, (r: T) => unknown>,
  initialKey?: string,
  initialDir: SortDir = "asc",
) {
  const [sortKey, setSortKey] = useState<string | null>(initialKey ?? null);
  const [dir, setDir] = useState<SortDir>(initialDir);

  let sorted = rows;
  if (sortKey && accessors[sortKey]) {
    const acc = accessors[sortKey];
    sorted = [...rows].sort((a, b) => {
      const va = acc(a);
      const vb = acc(b);
      if (va == null && vb == null) return 0;
      if (va == null) return 1;
      if (vb == null) return -1;
      const cmp =
        typeof va === "number" && typeof vb === "number"
          ? va - vb
          : String(va).localeCompare(String(vb), undefined, { numeric: true });
      return dir === "asc" ? cmp : -cmp;
    });
  }

  const toggle = (key: string) => {
    if (sortKey === key) {
      setDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setDir("asc");
    }
  };

  return { sorted, sortKey, dir, toggle };
}

/** Clickable table header cell that shows the current sort direction. */
export function SortTh({
  label,
  sortKey: k,
  activeKey,
  dir,
  onSort,
  className = "",
}: {
  label: string;
  sortKey: string;
  activeKey: string | null;
  dir: SortDir;
  onSort: (key: string) => void;
  className?: string;
}) {
  const active = activeKey === k;
  const Icon = !active ? ChevronsUpDown : dir === "asc" ? ChevronUp : ChevronDown;
  return (
    <th
      className={`cursor-pointer select-none whitespace-nowrap ${className}`}
      onClick={() => onSort(k)}
    >
      <span className="inline-flex items-center gap-1">
        {label}
        <Icon size={12} className={active ? "text-brand-500" : "opacity-40"} />
      </span>
    </th>
  );
}
