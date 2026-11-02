"use client";
/**
 * The customer who asked ("Customer asked" flow): the complaint as customer service passed it on and how long they had
 * waited. The hub never talks to the customer; this is the trace request. What it offers depends on where the case is
 * (Rexton 2 Nov: the update must not skip "Go look"): while staff have not looked yet, a HOLDING reply drafted in place
 * (traced to the hub, being checked, when they will hear next; no internal detail, nothing sent, editable, copy);
 * once the parcel is found or the case is closed, the full update on the Report.
 */
import Link from "next/link";
import { useId, useState } from "react";
import { ago, waited } from "@/components/hub/parts";
import "@/app/hub/hub.css";
import "./customerbox.css";

const day = (iso: string) => new Date(iso).toLocaleDateString("en-GB", { timeZone: "Asia/Kuala_Lumpur", day: "numeric", month: "short" });

export function CustomerBox({ caseId, complaint, opened, lastScan, waybill, settled = false }: {
  caseId: string; complaint: string; opened: string; lastScan?: string; waybill?: string;
  /** found on the floor or closed: the full update is ready on the Report */
  settled?: boolean;
}) {
  const wait = lastScan ? waited(lastScan, opened) : null;
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const id = useId();
  const draft = `Hello, thank you for your patience. We have traced your parcel${waybill ? ` ${waybill}` : ""} to our sorting hub`
    + `${lastScan ? `, where it was last recorded on ${day(lastScan)}` : ""}. Our team is checking the hub for it now, `
    + "and we will update you within one working day.";
  const [text, setText] = useState<string | null>(null);
  const copy = async () => {
    try { await navigator.clipboard.writeText(text ?? draft); setCopied(true); window.setTimeout(() => setCopied(false), 1800); } catch { /* the text stays selectable */ }
  };
  return (
    <section className="cu" aria-label="The customer who asked">
      <p className="cu-label"><b>Customer asked</b>{wait ? ` · waited ${wait} after its last scan here` : " · trace request from customer service"}<span> · case opened {ago(opened)}</span></p>
      <blockquote className="cu-quote"><p>&ldquo;{complaint}&rdquo;</p></blockquote>
      {settled ? (
        <Link className="hb-btn cu-go" href={`/cases/${caseId}/report#customer`}>Draft the update to the customer</Link>
      ) : (
        <>
          <button type="button" className="hb-btn cu-go" aria-expanded={open} aria-controls={id} onClick={() => setOpen((v) => !v)}>
            {open ? "Hide the holding reply" : "Draft a holding reply"}
          </button>
          <div className="cu-draft" id={id} data-open={open ? "" : undefined} inert={!open}>
            <div className="cu-draft-in">
              <label className="cu-draft-label" htmlFor={`${id}-t`}>For customer service to send while staff look · nothing is sent from here</label>
              <textarea id={`${id}-t`} className="cu-draft-text" rows={4} value={text ?? draft} onChange={(e) => setText(e.target.value)} />
              <div className="cu-draft-acts">
                <button type="button" className="hb-btn hb-btn-primary" onClick={copy}>{copied ? "Copied" : "Copy the reply"}</button>
                <span>The full update comes with the report, after staff have looked.</span>
              </div>
            </div>
          </div>
        </>
      )}
    </section>
  );
}
