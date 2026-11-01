import type { Metadata } from "next";
import { Landing } from "@/components/landing/Landing";

export const metadata: Metadata = {
  title: "Spoor · Every parcel leaves a trail",
  description: "Spoor reads your hub's CCTV and scan records, finds where a missing parcel went, and hands you the clip that proves it.",
};

export default function Home() {
  return <Landing />;
}
