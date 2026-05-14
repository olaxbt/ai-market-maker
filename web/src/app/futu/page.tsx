import { redirect } from "next/navigation";

/** Standalone URL; console shell + nav live at `/console?view=futu`. */
export default function Page() {
  redirect("/console?view=futu");
}
