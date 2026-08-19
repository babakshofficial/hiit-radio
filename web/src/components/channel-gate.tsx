"use client";

import { useAuth } from "@/lib/auth";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

export function ChannelGate({ children }: { children: React.ReactNode }) {
  const { accessAllowed, channelJoinUrl, refreshAccess } = useAuth();

  if (accessAllowed === null) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center text-muted-foreground">
        بررسی عضویت کانال…
      </div>
    );
  }

  if (!accessAllowed) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center p-4">
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle>عضویت در کانال لازم است</CardTitle>
            <CardDescription>
              برای استفاده از HiiT Radio ابتدا در کانال عضو شوید، سپس دوباره بررسی کنید.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            {channelJoinUrl && (
              <Button
                render={<a href={channelJoinUrl} target="_blank" rel="noreferrer" />}
              >
                عضویت در کانال
              </Button>
            )}
            <Button variant="outline" onClick={() => refreshAccess()}>
              بررسی مجدد
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return <>{children}</>;
}
