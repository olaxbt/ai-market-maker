import { redirect } from "next/navigation";

export default function PlatformLoginRedirectPage() {
  redirect("/console?view=research");
}
