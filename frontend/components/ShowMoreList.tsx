"use client";

import { useRef, useState } from "react";

import { Button } from "@/components/ui";

interface Props<T> {
  items: T[];
  /** Plural noun for the button and the count, e.g. "blood banks". */
  noun: string;
  /** How many to show at first and to add per click. */
  pageSize?: number;
  /** Must return an <li>. */
  renderItem: (item: T, index: number) => React.ReactNode;
  className?: string;
}

/**
 * Shows the first `pageSize` items (nearest first) and a "Load more" button
 * that adds `pageSize` more. After loading, focus moves to the first new item
 * so keyboard and screen-reader users continue from where the list grew.
 *
 * Give it a `key` that changes with each new search so it starts again at 5.
 */
export function ShowMoreList<T>({ items, noun, pageSize = 5, renderItem, className = "space-y-3" }: Props<T>) {
  const [shown, setShown] = useState(pageSize);
  const list = useRef<HTMLUListElement>(null);
  const visible = items.slice(0, shown);
  const remaining = items.length - visible.length;

  function loadMore() {
    const firstNew = visible.length;
    setShown((n) => n + pageSize);
    requestAnimationFrame(() => {
      const item = list.current?.children[firstNew] as HTMLElement | undefined;
      if (!item) return;
      item.tabIndex = -1;
      item.focus();
    });
  }

  return (
    <>
      <ul ref={list} className={className}>
        {visible.map(renderItem)}
      </ul>
      <p className="mt-3 text-center text-xs text-muted" aria-live="polite">
        Showing {visible.length} of {items.length} {noun}
      </p>
      {remaining > 0 && (
        <Button variant="secondary" className="mt-2 w-full" onClick={loadMore}>
          Load {Math.min(pageSize, remaining)} more {noun}
        </Button>
      )}
    </>
  );
}
