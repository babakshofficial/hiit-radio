"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Download, Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import EmptyState from "@/components/shadcn-space/blocks/empty-state-01/empty-state";

type Item = {
  id?: number;
  title?: string;
  artist?: string;
  content_key?: string;
};

export default function LikedPage() {
  const router = useRouter();
  const [items, setItems] = useState<Item[]>([]);
  const [loading, setLoading] = useState(true);

  async function load() {
    const res = await api<{ items: Item[] }>("/liked?limit=50");
    setItems(res.items || []);
  }

  useEffect(() => {
    load()
      .catch((e) => toast.error(e instanceof Error ? e.message : "خطا"))
      .finally(() => setLoading(false));
  }, []);

  async function remove(key: string) {
    try {
      await api(`/liked/${encodeURIComponent(key)}`, { method: "DELETE" });
      setItems((prev) => prev.filter((i) => i.content_key !== key));
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "خطا");
    }
  }

  async function download(item: Item) {
    try {
      await api("/jobs/download", {
        method: "POST",
        body: JSON.stringify({
          query: [item.title, item.artist].filter(Boolean).join(" "),
        }),
      });
      toast.success("دانلود شروع شد");
      router.push("/");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "خطا");
    }
  }

  if (loading) return <p className="text-muted-foreground">بارگذاری…</p>;
  if (!items.length) {
    return (
      <EmptyState
        title="علاقه‌مندی خالی است"
        description="با دکمه قلب روی آهنگ‌ها، اینجا جمع می‌شوند."
        primaryAction={{
          label: "برو به خانه",
          onClick: () => router.push("/"),
        }}
      />
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold">علاقه‌مندی‌ها</h1>
      {items.map((item) => (
        <Card key={item.content_key || item.id}>
          <CardContent className="flex items-center justify-between gap-3 py-4">
            <div>
              <p className="font-medium">{item.title}</p>
              <p className="text-sm text-muted-foreground">{item.artist}</p>
            </div>
            <div className="flex gap-1">
              <Button size="icon-sm" variant="outline" onClick={() => download(item)}>
                <Download />
              </Button>
              {item.content_key && (
                <Button
                  size="icon-sm"
                  variant="ghost"
                  onClick={() => remove(item.content_key!)}
                >
                  <Trash2 />
                </Button>
              )}
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
