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
      <p className="cu-label"><b>Customer asked</b>{wait ? ` · waited ${wait} after its last scan here` : " · trace request from customer service"}<span> · case opened {ago(opened)}</span></p>
      <blockquote className="cu-quote"><p>&ldquo;{complaint}&rdquo;</p></blockquote>
      <Link className="hb-btn cu-go" href={`/cases/${caseId}/report#customer`}>Draft the update to the customer</Link>
    </section>
  );
}
