import type { Metadata } from "next";
import { IBM_Plex_Mono, Inter, Noto_Sans_Devanagari } from "next/font/google";
import { Sidebar } from "@/components/shell/Sidebar";
import "./globals.css";

const sans = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

const mono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-mono",
  display: "swap",
});

const devanagari = Noto_Sans_Devanagari({
  subsets: ["devanagari"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-devanagari",
  display: "swap",
});

export const metadata: Metadata = {
  title: "SANKET, Standing Watch",
  description: "National glacial-hazard watch for Nepal",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${sans.variable} ${mono.variable} ${devanagari.variable}`}>
      <body className="min-h-screen antialiased">
        <div className="flex min-h-screen">
          <Sidebar />
          <div className="min-w-0 flex-1">{children}</div>
        </div>
      </body>
    </html>
  );
}
