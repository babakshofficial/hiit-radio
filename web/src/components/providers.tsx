"use client";

import { AuthProvider } from "@/lib/auth";
import { LoginGate } from "@/components/login-gate";
import { ChannelGate } from "@/components/channel-gate";
import { AppShell } from "@/components/app-shell";
import { Toaster } from "@/components/ui/sonner";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      <LoginGate>
        <AppShell>
          <ChannelGate>{children}</ChannelGate>
        </AppShell>
      </LoginGate>
      <Toaster richColors position="top-center" />
    </AuthProvider>
  );
}
