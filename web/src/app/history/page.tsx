"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Download, Heart } from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import EmptyState from "@/components/shadcn-space/blocks/empty-state-01/empty-state";

type Item = {
  id?: number;
  title?: string;
  artist?: string;
  album?: string;
  platform?: string;
  created_at?: number;
};

export default function HistoryPage() {
  const [items, setItems] = useState<Item[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const res = await api<{ items: Item[] }>("/history?limit=50");
        setItems(res.items || []);
      } catch (e) {
        toast.error(e instanceof Error ? e.message : "خطا");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  async function redownload(item: Item) {
    const q = [item.title, item.artist].filter(Boolean).join(" ");
    try {
      await api("/jobs/download", {
        method: "POST",
        body: JSON.stringify({ query: q }),
      });
      toast.success("دانلود شروع شد — به خانه بروید");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "خطا");
    }
  }

  async function like(item: Item) {
    try {
      await api("/liked", {
        method: "POST",
        body: JSON.stringify({
          title: item.title,
          artist: item.artist,
          album: item.album,
        }),
      });
      toast.success("به علاقه‌مندی‌ها اضافه شد");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "خطا");
    }
  }

  if (loading) return <p className="text-muted-foreground">بارگذاری…</p>;
  if (!items.length) {
    return (
      <EmptyState
        title="تاریخی نیست"
        description="بعد از اولین دانلود، اینجا نمایش داده می‌شود."
        primaryAction={{
          label: "برو به خانه",
          onClick: () => {
            window.location.href = "/";
          },
        }}
      />
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold">تاریخچه</h1>
      <div className="flex flex-col gap-2">
        {items.map((item) => (
          <Card key={item.id}>
            <CardContent className="flex items-center justify-between gap-3 py-4">
              <div>
                <p className="font-medium">{item.title}</p>
                <p className="text-sm text-muted-foreground">{item.artist}</p>
              </div>
              <div className="flex gap-1">
                <Button size="icon-sm" variant="ghost" onClick={() => like(item)}>
                  <Heart />
                </Button>
                <Button size="icon-sm" variant="outline" onClick={() => redownload(item)}>
                  <Download />
                </Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
