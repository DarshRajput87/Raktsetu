"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { Button } from "@/components/ui";
import { useAuth } from "@/lib/auth";

const LINKS = [
  { href: "/", label: "Find blood" },
  { href: "/donor/register", label: "Donate" },
  { href: "/hospital", label: "Hospital" },
  { href: "/bank", label: "Blood bank" },
  { href: "/admin", label: "Admin" },
];

const ROLE_LABELS = { public: "Signed in", donor: "Donor", hospital: "Hospital", bank_admin: "Blood bank", admin: "Admin" };

export function Header() {
  const pathname = usePathname();
  const { user, signOut } = useAuth();
  const links = user?.role === "donor" ? LINKS.map((l) => (l.href === "/donor/register" ? { href: "/donor/me", label: "My donor profile" } : l)) : LINKS;

  return (
    <header className="border-b border-line bg-white">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-1 px-4 py-2">
        <Link href="/" className="flex items-center gap-2 py-1 text-lg font-bold tracking-tight">
          <span aria-hidden="true" className="grid size-7 place-items-center rounded-md bg-accent text-sm text-white">
            R
          </span>
          RaktSetu
        </Link>
        <nav aria-label="Main" className="order-3 -mx-2 flex w-full gap-1 overflow-x-auto sm:order-none sm:mx-0 sm:w-auto">
          {links.map((link) => {
            const current = link.href === "/" ? pathname === "/" : pathname.startsWith(link.href);
            return (
              <Link
                key={link.href}
                href={link.href}
                aria-current={current ? "page" : undefined}
                className={`whitespace-nowrap rounded-md px-2 py-2 text-sm font-medium ${
                  current ? "text-accent underline decoration-2 underline-offset-8" : "text-ink hover:text-accent"
                }`}
              >
                {link.label}
              </Link>
            );
          })}
        </nav>
        {user && (
          <div className="ml-auto flex min-w-0 items-center gap-2 text-sm">
            <span className="truncate text-muted" title={user.name ?? user.phone ?? undefined}>
              {ROLE_LABELS[user.role]}
              {user.name ? `: ${user.name}` : ""}
            </span>
            <Button variant="ghost" onClick={signOut}>
              Log out
            </Button>
          </div>
        )}
      </div>
    </header>
  );
}
