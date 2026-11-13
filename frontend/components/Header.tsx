"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { IconBank, IconDrop, IconHospital, IconLogout, IconSearch, IconShield, IconUser } from "@/components/icons";
import { useAuth } from "@/lib/auth";
import type { Role } from "@/lib/types";

const LINKS = [
  { href: "/", label: "Find blood", icon: IconSearch },
  { href: "/donor/register", label: "Donate", icon: IconDrop },
  { href: "/hospital", label: "Hospital", icon: IconHospital },
  { href: "/bank", label: "Blood bank", icon: IconBank },
  { href: "/admin", label: "Admin", icon: IconShield },
];

const ROLE_LABELS: Record<Role, string> = {
  public: "Signed in",
  donor: "Donor",
  hospital: "Hospital",
  bank_admin: "Blood bank",
  admin: "System admin",
};

/** The RaktSetu mark: a drop on a red tile, with the name in Latin and Devanagari. */
export function Wordmark() {
  return (
    <Link href="/" className="group flex items-center gap-2.5 rounded-lg py-1 pr-1" aria-label="RaktSetu home">
      <span aria-hidden="true" className="grid size-8 place-items-center rounded-[9px] bg-accent text-white shadow-[var(--shadow-accent)]">
        <IconDrop size={18} className="fill-white/25" />
      </span>
      <span aria-hidden="true" className="flex items-baseline gap-2">
        <span className="text-[17px] font-semibold tracking-tight text-ink">RaktSetu</span>
        <span lang="hi" className="hidden font-[family-name:var(--font-deva)] text-[13px] text-muted sm:inline">
          रक्तसेतु
        </span>
      </span>
    </Link>
  );
}

export function Header() {
  const pathname = usePathname();
  const { user, signOut } = useAuth();
  const links =
    user?.role === "donor"
      ? LINKS.map((l) => (l.href === "/donor/register" ? { ...l, href: "/donor/me", label: "My profile" } : l))
      : LINKS;
  const isCurrent = (href: string) =>
    href === "/" ? pathname === "/" : pathname.startsWith(href.startsWith("/donor") ? "/donor" : href);

  return (
    <>
      <header className="sticky top-0 z-[1100] border-b border-line bg-white/85 backdrop-blur-md supports-[backdrop-filter]:bg-white/75">
        <div className="mx-auto flex h-14 max-w-[1320px] items-center gap-6 px-4 sm:px-6">
          <Wordmark />

          <nav aria-label="Main" className="hidden items-center gap-0.5 md:flex">
            {links.map((link) => {
              const current = isCurrent(link.href);
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  aria-current={current ? "page" : undefined}
                  className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
                    current ? "bg-accent-soft text-accent-dark" : "text-muted hover:bg-surface hover:text-ink"
                  }`}
                >
                  {link.label}
                </Link>
              );
            })}
          </nav>

          {user && (
            <div className="ml-auto flex min-w-0 items-center gap-1">
              <span
                className="flex min-w-0 items-center gap-2 rounded-full bg-surface py-1 pl-1 pr-3 text-[13px]"
                title={user.name ?? user.phone ?? undefined}
              >
                <span aria-hidden="true" className="grid size-6 shrink-0 place-items-center rounded-full bg-white text-muted shadow-[var(--shadow-raise)]">
                  <IconUser size={14} />
                </span>
                <span className="truncate">
                  <span className="font-medium text-ink">{ROLE_LABELS[user.role]}</span>
                  {user.name && user.name.toLowerCase() !== ROLE_LABELS[user.role].toLowerCase() && (
                    <span className="hidden text-muted lg:inline">, {user.name}</span>
                  )}
                </span>
              </span>
              <button
                type="button"
                onClick={signOut}
                className="flex min-h-9 items-center gap-1.5 rounded-lg px-2.5 text-[13px] font-medium text-muted transition-colors hover:bg-surface hover:text-ink"
              >
                <IconLogout size={16} />
                Log out
              </button>
            </div>
          )}
        </div>
      </header>

      {/* Phones: the same links as a bottom tab bar, within reach of a thumb. */}
      <nav
        aria-label="Main"
        className="fixed inset-x-0 bottom-0 z-[1100] border-t border-line bg-white/95 pb-[env(safe-area-inset-bottom)] backdrop-blur-md md:hidden"
      >
        <ul className="grid grid-cols-5">
          {links.map((link) => {
            const current = isCurrent(link.href);
            const Icon = link.icon;
            return (
              <li key={link.href}>
                <Link
                  href={link.href}
                  aria-current={current ? "page" : undefined}
                  className={`flex min-h-14 flex-col items-center justify-center gap-0.5 text-[11px] font-medium transition-colors ${
                    current ? "text-accent" : "text-muted"
                  }`}
                >
                  <Icon size={21} className={current ? "fill-accent/10" : ""} />
                  {link.label}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
    </>
  );
}
