"use client";
/** The case header from review/refs/flow: breadcrumb (Hub › waybill · what the customer said) and the 4 numbered steps. */
import Link from "next/link";
import "./flow.css";

const STEPS = [["", "1 Answer"], ["/proof", "2 Proof"], ["/search", "3 Go look"], ["/report", "4 Report"]] as const;

export function CaseSteps({ caseId, waybill, said, page, here }: { caseId: string; waybill: string; said?: string | null; page?: string; here: 0 | 1 | 2 | 3 }) {
  return (
    <div className="fl-casebar">
      <p className="fl-crumb"><Link href="/hub">Hub</Link> <span aria-hidden="true">›</span> {page ? <Link href={`/cases/${caseId}`}>{waybill}</Link> : <span className="fl-crumb-wb">{waybill}</span>}{said ? ` · ${said}` : ""}
        {page && <> <span aria-hidden="true">›</span> <span className="fl-crumb-wb">{page}</span></>}</p>
      <nav aria-label="Case steps" className="fl-steps">
        {STEPS.map(([path, label], i) => (
          <Link key={label} href={`/cases/${caseId}${path}`} aria-current={i === here ? "page" : undefined}>{label}</Link>
        ))}
      </nav>
    </div>
  );
}
