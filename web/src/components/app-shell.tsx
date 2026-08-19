"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Compass,
  Heart,
  Home,
  LogOut,
  Shield,
  Star,
  Trophy,
  UserPlus,
  History,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/auth";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";

const NAV = [
  { href: "/", label: "خانه", icon: Home },
  { href: "/history", label: "تاریخچه", icon: History },
  { href: "/liked", label: "علاقه‌مندی", icon: Heart },
  { href: "/charts", label: "چارت", icon: Trophy },
  { href: "/discover", label: "کشف", icon: Compass },
  { href: "/premium", label: "پرمیوم", icon: Star },
  { href: "/invite", label: "دعوت", icon: UserPlus },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { user, quota, logout } = useAuth();

  const quotaLabel =
    quota?.limit == null
      ? "نامحدود"
      : `${quota.used}/${quota.limit}`;

  return (
    <div className="min-h-dvh bg-background text-foreground flex flex-col">
      <header className="sticky top-0 z-40 border-b bg-background/90 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-3xl items-center justify-between gap-3 px-4">
          <div className="flex items-center gap-2">
            <Sheet>
              <SheetTrigger
                className="md:hidden inline-flex h-7 items-center rounded-lg px-2.5 text-sm hover:bg-muted"
              >
                منو
              </SheetTrigger>
              <SheetContent side="right" className="w-72">
                <SheetHeader>
                  <SheetTitle>HiiT Radio</SheetTitle>
                </SheetHeader>
                <nav className="mt-4 flex flex-col gap-1">
                  {NAV.map((item) => (
                    <Link
                      key={item.href}
                      href={item.href}
                      className={cn(
                        "flex items-center gap-2 rounded-lg px-3 py-2 text-sm",
                        pathname === item.href
                          ? "bg-primary text-primary-foreground"
                          : "hover:bg-muted",
                      )}
                    >
                      <item.icon className="size-4" />
                      {item.label}
                    </Link>
                  ))}
                  {user?.is_admin && (
                    <Link
                      href="/admin"
                      className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm hover:bg-muted"
                    >
                      <Shield className="size-4" />
                      Admin
                    </Link>
                  )}
                </nav>
              </SheetContent>
            </Sheet>
            <Link href="/" className="font-semibold tracking-tight">
              HiiT Radio
            </Link>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="font-normal">
              {quota?.tier || "—"} · {quotaLabel}
            </Badge>
            <Avatar className="size-8">
              {user?.photo_url ? (
                <AvatarImage src={user.photo_url} alt="" />
              ) : null}
              <AvatarFallback>
                {(user?.first_name || user?.username || "?").slice(0, 1)}
              </AvatarFallback>
            </Avatar>
            <Button variant="ghost" size="icon-sm" onClick={logout} title="خروج">
              <LogOut className="size-4" />
            </Button>
          </div>
        </div>
        <nav className="mx-auto hidden max-w-3xl gap-1 overflow-x-auto px-4 pb-2 md:flex">
          {NAV.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs whitespace-nowrap",
                pathname === item.href
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted text-muted-foreground hover:text-foreground",
              )}
            >
              <item.icon className="size-3.5" />
              {item.label}
            </Link>
          ))}
          {user?.is_admin && (
            <Link
              href="/admin"
              className={cn(
                "inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs",
                pathname === "/admin"
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted",
              )}
            >
              <Shield className="size-3.5" />
              Admin
            </Link>
          )}
        </nav>
      </header>
      <main className="mx-auto w-full max-w-3xl flex-1 px-4 py-6">{children}</main>
    </div>
  );
}
