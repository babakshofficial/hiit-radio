"use client";

import { useEffect } from "react";
import { useAuth } from "@/lib/auth";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

export function LoginGate({ children }: { children: React.ReactNode }) {
  const { ready, token, inTelegram, botUsername, authWithLoginWidget } = useAuth();

  useEffect(() => {
    if (!ready || token || inTelegram) return;
    window.onTelegramAuth = async (user) => {
      try {
        await authWithLoginWidget(user);
      } catch (e) {
        console.error(e);
        alert(e instanceof Error ? e.message : "ورود ناموفق");
      }
    };

    const existing = document.getElementById("telegram-login-script");
    if (existing) existing.remove();

    const script = document.createElement("script");
    script.id = "telegram-login-script";
    script.src = "https://telegram.org/js/telegram-widget.js?22";
    script.async = true;
    script.setAttribute("data-telegram-login", botUsername);
    script.setAttribute("data-size", "large");
    script.setAttribute("data-radius", "8");
    script.setAttribute("data-onauth", "onTelegramAuth(user)");
    script.setAttribute("data-request-access", "write");
    const mount = document.getElementById("telegram-login-mount");
    if (mount) {
      mount.innerHTML = "";
      mount.appendChild(script);
    }
  }, [ready, token, inTelegram, botUsername, authWithLoginWidget]);

  if (!ready) {
    return (
      <div className="flex min-h-dvh items-center justify-center text-muted-foreground">
        در حال بارگذاری…
      </div>
    );
  }

  if (!token) {
    return (
      <div className="flex min-h-dvh items-center justify-center p-6">
        <Card className="w-full max-w-md">
          <CardHeader className="text-center">
            <CardTitle className="text-2xl">HiiT Radio</CardTitle>
            <CardDescription>
              برای دانلود آهنگ با همان حساب تلگرام وارد شوید
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col items-center gap-4">
            <div id="telegram-login-mount" className="min-h-12" />
            <p className="text-center text-xs text-muted-foreground">
              دامنه سایت باید در BotFather برای Login Widget فعال باشد.
            </p>
            <Button
              variant="outline"
              onClick={() =>
                window.open(`https://t.me/${botUsername}`, "_blank")
              }
            >
              باز کردن ربات در تلگرام
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return <>{children}</>;
}
