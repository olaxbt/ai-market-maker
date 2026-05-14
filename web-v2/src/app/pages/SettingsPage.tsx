import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import PlatformProvidersPage from "./PlatformProvidersPage";

export default function SettingsPage() {
  return (
    <div className="px-4 pb-10 sm:px-6">
      <div className="mx-auto w-full max-w-6xl space-y-6">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Access</CardTitle>
            <CardDescription>Provider keys and publishing access.</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="text-sm text-muted-foreground">
                Sign in from the sidebar account item to create and rotate provider keys.
              </div>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => window.dispatchEvent(new CustomEvent("aimm:open-login"))}
              >
                Sign in
              </Button>
            </div>

            <div className="mt-4">
              <PlatformProvidersPage embedded />
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

