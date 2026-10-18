import type { Metadata } from "next";
import { Inter, Inter_Tight, JetBrains_Mono } from "next/font/google";
import Link from "next/link";
import { HealthDot } from "@/components/HealthDot";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });
const interTight = Inter_Tight({ subsets: ["latin"], variable: "--font-inter-tight" });
const jetbrains = JetBrains_Mono({ subsets: ["latin"], variable: "--font-jetbrains" });

export const metadata: Metadata = {
  title: "Landfall",
  description: "Did an FDA boxed warning land on the label of record for this NDC?",
};

const links = [
  ["/", "Check an NDC"],
  ["/facts/montelukast_bw_2020", "Facts"],
  ["/replay", "Replay"],
  ["/orgs", "Organisations"],
  ["/checks", "Checks"],
  ["/mcp", "MCP"],
  ["/eval", "Eval"],
  ["/how-it-works", "How it works"],
] as const;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body
        className={`${inter.variable} ${interTight.variable} ${jetbrains.variable} min-h-screen`}
      >
        <header className="border-b border-white/10 bg-[#161d25]">
          <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3">
            <Link
              href="/"
              className="text-lg font-semibold tracking-tight"
              style={{ fontFamily: "var(--font-inter-tight)" }}
            >
              Landfall
            </Link>
            <nav className="flex flex-wrap gap-x-3 gap-y-1 text-sm text-[#98a3b1]">
              {links.map(([href, label]) => (
                <Link key={href} href={href} className="hover:text-[#e6ebf0]">
                  {label}
                </Link>
              ))}
            </nav>
            <HealthDot />
          </div>
        </header>
        <main className="mx-auto max-w-6xl px-4 py-8">{children}</main>
        <footer className="mx-auto max-w-6xl px-4 pb-8 text-sm text-[#98a3b1]">
          Built for Graph Hacks with FalkorDB · Data: DailyMed (NLM) and openFDA (FDA) public data ·
          Automated screening, not medical, legal or regulatory advice · Not endorsed by FDA or NLM
          · Organisations shown are fictional.
        </footer>
      </body>
    </html>
  );
}
