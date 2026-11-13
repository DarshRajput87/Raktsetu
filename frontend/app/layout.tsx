import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";

import { Header } from "@/components/Header";
import { AuthProvider } from "@/lib/auth";

import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: { default: "RaktSetu: find blood near you", template: "%s | RaktSetu" },
  description:
    "Find the nearest blood bank with compatible stock, with the road route to it. If no bank has stock, see matching donors nearby.",
};

export const viewport: Viewport = { themeColor: "#b3202f" };

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col">
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-[2000] focus:rounded-md focus:bg-white focus:px-3 focus:py-2"
        >
          Skip to content
        </a>
        <AuthProvider>
          <Header />
          <main id="main" className="mx-auto w-full max-w-6xl flex-1 px-4 py-5">
            {children}
          </main>
        </AuthProvider>
        <footer className="border-t border-line px-4 py-3 text-center text-xs text-muted">
          RaktSetu, an M.Tech project. Demo data: names and phone numbers are not real. Map data ©
          OpenStreetMap contributors.
        </footer>
      </body>
    </html>
  );
}
