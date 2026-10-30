import type { Metadata, Viewport } from "next";
import "@fontsource-variable/google-sans-flex";
import "./globals.css";
import "./style-v2.css";
import { Shell } from "@/components/Shell";

export const metadata: Metadata = {
  title: "Spoor · investigation workspace",
  description: "Evidence-grounded parcel investigation on a fictional hub. Synthetic footage, simulated scans.",
};

export const viewport: Viewport = { width: "device-width", initialScale: 1, themeColor: "#0e1012" };

const STYLE_BOOT = `try{var q=new URLSearchParams(location.search).get("style");if(q)localStorage.setItem("spoor-style",q);
var s=q||localStorage.getItem("spoor-style");if(s==="v2")document.documentElement.dataset.style="v2"}catch(e){}`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        {/* Style v2 preview (owner_style_0136) until Rexton approves: ?style=v2 turns it on and remembers it,
            ?style=v1 turns it off. Set before first paint so nothing flashes. */}
        <script dangerouslySetInnerHTML={{ __html: STYLE_BOOT }} />
      </head>
      <body>
        <Shell>{children}</Shell>
      </body>
    </html>
  );
}
