import { redirect } from "next/navigation";

export default function PlatformProvidersRedirectPage() {
  redirect("/console?view=research");
}
