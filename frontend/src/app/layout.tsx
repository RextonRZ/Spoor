import type { Metadata, Viewport } from "next";
import "@fontsource-variable/google-sans-flex";
import "./globals.css";
import "./style-v2.css";
import { Inter } from "next/font/google";
import { Shell } from "@/components/Shell";

// the prototype's face (review/refs/flow): Inter, then Google Sans Flex
const inter = Inter({ subsets: ["latin"], weight: ["400", "500", "600", "700"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: "Spoor",
  description: "Every parcel leaves a trail. Spoor reads it.",
};

export const viewport: Viewport = { width: "device-width", initialScale: 1, themeColor: "#0e1012" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    // one look (owner 09:04): the v2 tokens are the app's only style; the ?style switch is gone
    <html lang="en" data-style="v2" className={inter.variable}>
      <body>
        <Shell>{children}</Shell>
      </body>
    </html>
  );
}
