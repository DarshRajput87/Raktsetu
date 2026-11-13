import type { Metadata, Viewport } from "next";
import { Instrument_Sans, Noto_Sans_Devanagari } from "next/font/google";

import { Header } from "@/components/Header";
import { AuthProvider } from "@/lib/auth";

import "./globals.css";

// One family for the whole interface; Devanagari only for the wordmark (रक्तसेतु).
const instrument = Instrument_Sans({ variable: "--font-instrument", subsets: ["latin"], display: "swap" });
const devanagari = Noto_Sans_Devanagari({ variable: "--font-deva", subsets: ["devanagari"], weight: ["600"], display: "swap" });

export const metadata: Metadata = {
  title: { default: "RaktSetu: find blood near you", template: "%s | RaktSetu" },
  description:
    "Find the nearest blood bank with compatible stock, with the road route to it. If no bank has stock, see matching donors nearby.",
};

export const viewport: Viewport = { themeColor: "#b3202f" };

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${instrument.variable} ${devanagari.variable} h-full antialiased`}>
      {/* Browser extensions (e.g. ColorZilla's cz-shortcut-listen) add attributes to <body>
          before React loads; this silences that one-level hydration warning only. */}
      <body className="flex min-h-full flex-col pb-[calc(3.5rem+env(safe-area-inset-bottom))] md:pb-0" suppressHydrationWarning>
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-[2000] focus:rounded-lg focus:bg-white focus:px-3 focus:py-2 focus:shadow-[var(--shadow-float)]"
        >
          Skip to content
        </a>
        <AuthProvider>
          <Header />
          <main id="main" className="mx-auto w-full max-w-[1320px] flex-1 px-4 py-6 sm:px-6 sm:py-8">
            {children}
          </main>
        </AuthProvider>
        <footer className="border-t border-line bg-white">
          <div className="mx-auto flex max-w-[1320px] flex-wrap items-center justify-between gap-x-6 gap-y-1 px-4 py-4 text-xs text-muted sm:px-6">
            <p>RaktSetu, an M.Tech project. Demo data: names and phone numbers are not real.</p>
            <p>Map data © OpenStreetMap contributors</p>
          </div>
        </footer>
      </body>
    </html>
  );
}
