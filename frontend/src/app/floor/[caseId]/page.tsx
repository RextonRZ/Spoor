"use client";
/**
 * Spoor Floor on the worker's own phone: the app full screen, no console around it (Rexton 3 Nov). The supervisor's Go
 * look page shows the same app in a phone frame and links here.
 */
import { use, useEffect, useState } from "react";
import { useResource } from "@/lib/api";
import type { Journey } from "@/lib/journey";
import { FloorApp } from "@/components/golook/FloorApp";
import { waited } from "@/components/hub/parts";

interface CaseState { case: { target_description: string; created_at: string } }

export default function FloorPage({ params }: { params: Promise<{ caseId: string }> }) {
  const { caseId } = use(params);
  const st = useResource<CaseState>(`/v1/cases/${caseId}/state`);
  const jr = useResource<Journey>(`/v1/cases/${caseId}/journey`);
  const waybill = st.data?.case.target_description.split(" ").at(-1) ?? "";
  const last = jr.data?.objects[0]?.scans.at(-1);
  const wait = last && st.data ? waited(last.t, st.data.case.created_at) : null;
  // a computer opens it as the phone, centred and fitted to the window; a phone gets the app as the whole screen
  const [wide, setWide] = useState(false);
  useEffect(() => {
    const m = window.matchMedia("(min-width: 701px)"), f = () => setWide(m.matches);
    f(); m.addEventListener("change", f); return () => m.removeEventListener("change", f);
  }, []);
  if (wide) return <main className="floor-desk"><FloorApp caseId={caseId} waybill={waybill} waited={wait} center /></main>;
  return (
    <main className="fa-full">
      <FloorApp caseId={caseId} waybill={waybill} waited={wait} framed={false} />
    </main>
  );
}
