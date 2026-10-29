import type { Metadata, Viewport } from "next";
import "./globals.css";
import { Shell } from "@/components/Shell";

export const metadata: Metadata = {
  title: "Spoor · investigation workspace",
  description: "Evidence-grounded parcel investigation on a fictional hub. Synthetic footage, simulated scans.",
};

export const viewport: Viewport = { width: "device-width", initialScale: 1, themeColor: "#0e1012" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Shell>{children}</Shell>
      </body>
    </html>
  );
}
