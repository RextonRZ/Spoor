/**
 * The customer who asked ("Customer asked" flow): the complaint as customer service passed it on, how long they had
 * waited, and the way to the drafted update (Report). The hub never talks to the customer; this is the trace request.
 */
import Link from "next/link";
import { ago, waited } from "@/components/hub/parts";
import "@/app/hub/hub.css";
import "./customerbox.css";

export function CustomerBox({ caseId, complaint, opened, lastScan }: { caseId: string; complaint: string; opened: string; lastScan?: string }) {
  const wait = lastScan ? waited(lastScan, opened) : null;
  return (
    <section className="cu" aria-label="The customer who asked">
      <div className="cu-top">
        <span className="hb-chip" data-tone="ask">Customer asked</span>
        <span className="cu-meta">{wait ? `Waited ${wait} after its last scan here` : "Trace request from customer service"} · case opened {ago(opened)}</span>
      </div>
      <p className="cu-quote">&ldquo;{complaint}&rdquo;</p>
      <Link className="cu-go" href={`/cases/${caseId}/report#customer`}>Draft the update to the customer</Link>
    </section>
  );
}
