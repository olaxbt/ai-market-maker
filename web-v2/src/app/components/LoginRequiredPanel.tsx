export function LoginRequiredPanel({
  title = "Login required",
  body = "Sign in to continue.",
  cta = "Sign in",
}: {
  title?: string;
  body?: string;
  cta?: string;
}) {
  return (
    <section className="rounded-2xl border border-[rgba(0,212,170,0.22)] bg-[rgba(0,212,170,0.06)] p-4">
      <div className="text-[11px] font-semibold text-[rgba(0,212,170,0.95)]">
        {title}
      </div>
      <p className="mt-2 text-[12px] text-muted-foreground">{body}</p>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={() => window.dispatchEvent(new CustomEvent("aimm:open-login"))}
          className="rounded-xl border border-[rgba(0,212,170,0.25)] bg-[rgba(0,212,170,0.10)] px-3 py-2 text-[12px] font-semibold text-foreground hover:border-[rgba(0,212,170,0.45)]"
        >
          {cta}
        </button>
      </div>
    </section>
  );
}

