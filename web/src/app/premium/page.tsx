"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

type Product = { title: string; description: string; stars: number };

export default function PremiumPage() {
  const { inTelegram, botUsername, refreshMe, quota } = useAuth();
  const [products, setProducts] = useState<Record<string, Product>>({});
  const [checkout, setCheckout] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const res = await api<{
          products: Record<string, Product>;
          checkout_deep_link: string;
        }>("/premium/catalog");
        setProducts(res.products || {});
        setCheckout(res.checkout_deep_link);
      } catch (e) {
        toast.error(e instanceof Error ? e.message : "خطا");
      }
    })();
  }, []);

  async function buy(kind: string) {
    if (!inTelegram) {
      window.open(checkout || `https://t.me/${botUsername}?start=premium`, "_blank");
      toast.message("پرداخت با Stars فقط داخل تلگرام ممکن است");
      return;
    }
    try {
      const res = await api<{ invoice_url: string }>("/premium/invoice", {
        method: "POST",
        body: JSON.stringify({ kind }),
      });
      const tg = window.Telegram?.WebApp;
      if (tg?.openInvoice) {
        tg.openInvoice(res.invoice_url, (status) => {
          if (status === "paid") {
            toast.success("پرداخت موفق");
            refreshMe();
          } else {
            toast.message(status);
          }
        });
      } else {
        window.open(res.invoice_url, "_blank");
      }
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "خطا");
    }
  }

  const entries = Object.entries(products);

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold">پرمیوم</h1>
        <p className="text-sm text-muted-foreground">
          پلن فعلی: <Badge variant="outline">{quota?.tier}</Badge> · امروز{" "}
          {quota?.limit == null ? "نامحدود" : `${quota?.used}/${quota?.limit}`}
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        {entries.map(([kind, p]) => (
          <Card key={kind}>
            <CardHeader>
              <CardTitle className="text-base">{p.title}</CardTitle>
              <CardDescription>{p.description}</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-3">
              <p className="text-2xl font-semibold">{p.stars} ⭐</p>
              <Button onClick={() => buy(kind)}>خرید</Button>
            </CardContent>
          </Card>
        ))}
      </div>

      {!inTelegram && (
        <p className="text-sm text-muted-foreground">
          در وب، دکمه خرید شما را به ربات تلگرام برای پرداخت Stars هدایت می‌کند.
        </p>
      )}
    </div>
  );
}
