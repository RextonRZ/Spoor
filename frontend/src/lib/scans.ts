/**
 * What a scan or sorter event does and does not prove, in plain words (review 004 #1, #2).
 * Hub flow (fictional CONTOH hub): induction station -> infeed belt -> scan tunnel -> merge onto a cross-belt carrier
 * -> sorter loop -> chute. So "label read at the tunnel" comes BEFORE "loaded onto carrier"; a divert confirmation is
 * the sorter reporting where it tipped a tracked carrier, not a new label read.
 */
export interface ScanLike {
  event_kind: string;
  device_id: string;
  station_id?: string | null;
  read_outcome?: string;
  raw_code?: string | null;
  raw_description?: string | null;
  sort_destination_actual?: string | null;
}

export interface ScanWords {
  title: string; // short event name for labels and lists
  card: string; // source-type words after the evidence label, e.g. "sorter divert confirmation"
  proves: string;
}

export const HUB_FLOW = "induction station → infeed belt → scan tunnel → merge onto a carrier → sorter loop → chute";

function chuteFromDesc(s: ScanLike): string {
  const m = /chute\s+(\w+)/i.exec(s.raw_description ?? "");
  return m ? ` at ${m[1]}` : "";
}

function carrierOf(s: ScanLike): string | null {
  const m = /carrier\s+(\d+)/i.exec(s.raw_description ?? "");
  return m ? m[1] : null;
}

export function describeScan(s: ScanLike): ScanWords {
  const carrier = carrierOf(s);
  const chute = s.sort_destination_actual ?? s.station_id?.replace(/^SP-DIV-/, "") ?? null;
  const noRead = s.read_outcome && s.read_outcome !== "read";
  const code = s.raw_code ?? s.event_kind;
  switch (code) {
    case "tunnel_read":
      return { title: "label read at the scan tunnel", card: "scan tunnel label read",
        proves: "The tunnel read this parcel's label (with its size and weight). It does not show where the parcel went next." };
    case "tunnel_no_read":
      return { title: "tunnel no-read", card: "scan tunnel no-read",
        proves: "The tunnel saw a parcel but read no label. No identity: it cannot be tied to any waybill on its own." };
    case "induct_to_carrier":
      return noRead
        ? { title: `unidentified item loaded onto carrier ${carrier ?? "?"}`, card: "sorter carrier assignment, no identity",
          proves: "The sorter put an item it could not identify on a carrier." }
        : { title: `loaded onto carrier ${carrier ?? "?"}`, card: "sorter carrier assignment",
          proves: `The sorter assigned the tracked item to carrier ${carrier ?? "?"} at the merge. Identity is carried by sorter tracking from the tunnel read, not a new read.` };
    case "divert_confirm":
      return noRead
        ? { title: `unidentified item diverted to ${chute ?? "a chute"}`, card: "sorter divert, no identity",
          proves: `The sorter discharged a carrier at ${chute ?? "a chute"} holding an item it could not identify.` }
        : { title: `sorter divert to ${chute ?? "chute"}`, card: "sorter divert confirmation",
          proves: `The sorter reports carrier ${carrier ?? "?"} discharged at ${chute ?? "the chute"}. Identity comes from sorter tracking, not a new read. Whether the parcel then went into the bag is not shown.` };
    case "recirculate_chute_full":
      return { title: `recirculated: ${chute ?? "chute"} full`, card: "sorter recirculation",
        proves: `The sorter could not discharge carrier ${carrier ?? "?"} because the target chute was full; the item stays on the loop. Identity from sorter tracking, not a new read.` };
    case "bag_open":
      return { title: `new bag opened${chuteFromDesc(s)}`, card: "bag lifecycle scan (handheld)",
        proves: "A handheld scanned a new bag label at the chute. It is about the bag, not about any parcel." };
    case "bag_close":
      return { title: `bag closed${chuteFromDesc(s)}`, card: "bag lifecycle scan (handheld)",
        proves: "A handheld scanned the bag as closed. Which parcels are inside is not shown by this scan." };
    case "container_add":
      if (s.event_kind === "container_add" && /into/.test(s.raw_description ?? "")) {
        return { title: s.raw_description ?? "bag into roll cage", card: "container scan (handheld)",
          proves: "A handheld recorded this bag going into the roll cage. A parcel inside the bag inherits that place only as an estimate." };
      }
      break;
    case "reject_bin":
      return { title: "item into the reject chute", card: "reject chute event, no identity",
        proves: "Something without a readable identity entered the reject chute." };
  }
  const kind = s.event_kind.replace(/_/g, " ");
  return { title: kind, card: kind,
    proves: noRead ? "An event without an identity read." : "The identifier was recorded at this device. It does not show where the parcel went next." };
}
