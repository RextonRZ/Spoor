"use client";
/**
 * Spoor Floor on the worker's own phone: the app full screen, no console around it (Rexton 3 Nov). The supervisor's Go
 * look page shows the same app in a phone frame and links here.
 */
import { use } from "react";
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
  return (
    <main className="fa-full">
      <FloorApp caseId={caseId} waybill={waybill} waited={last && st.data ? waited(last.t, st.data.case.created_at) : null} framed={false} />
    </main>
  );
}
