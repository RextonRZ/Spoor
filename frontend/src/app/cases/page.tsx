import { redirect } from "next/navigation";

/** Cases live on the Hub (its Open cases and Resolved tabs): one list, one place. The old list is kept in CasesList.tsx
 *  for when volume calls for its own workspace. */
export default function CasesIndex() {
  redirect("/hub");
}
