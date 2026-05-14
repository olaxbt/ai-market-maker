import { Link, useLocation } from "react-router";
import { ArrowLeft, Home, Search } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Input } from "../components/ui/input";

export default function NotFoundPage() {
  const location = useLocation();
  const path = location.pathname + (location.search || "");

  return (
    <div className="flex-1 min-h-0 overflow-auto px-6 py-10">
      <div className="mx-auto w-full max-w-3xl">
        <Card>
          <CardHeader className="border-b">
            <CardTitle className="text-[16px]">Page not found</CardTitle>
            <CardDescription className="text-[12px]">
              Nothing matches <code className="text-foreground/90">{path}</code>
            </CardDescription>
          </CardHeader>
          <CardContent className="pt-4">
            <div className="grid gap-3">
              <div className="relative">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input className="pl-9" placeholder="Try: /leaderboard, /studio, /console, /trade" disabled />
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <Link
                  to="/"
                  className="inline-flex items-center gap-2 rounded-xl border border-border bg-card px-3 py-2 text-[12px] hover:bg-muted/30"
                >
                  <Home className="h-4 w-4" />
                  Home
                </Link>
                <Link
                  to="/leaderboard"
                  className="inline-flex items-center gap-2 rounded-xl border border-border bg-card px-3 py-2 text-[12px] hover:bg-muted/30"
                >
                  Leaderboard
                </Link>
                <Link
                  to="/studio"
                  className="inline-flex items-center gap-2 rounded-xl border border-border bg-card px-3 py-2 text-[12px] hover:bg-muted/30"
                >
                  Studio
                </Link>
                <Link
                  to="/console"
                  className="inline-flex items-center gap-2 rounded-xl border border-border bg-card px-3 py-2 text-[12px] hover:bg-muted/30"
                >
                  Console
                </Link>
                <button
                  type="button"
                  onClick={() => history.back()}
                  className="inline-flex items-center gap-2 rounded-xl border border-border bg-card px-3 py-2 text-[12px] hover:bg-muted/30"
                >
                  <ArrowLeft className="h-4 w-4" />
                  Back
                </button>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

