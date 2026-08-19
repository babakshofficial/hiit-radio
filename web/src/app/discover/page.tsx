"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Sparkles } from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

type Item = { title?: string; artist?: string };

export default function DiscoverPage() {
  const router = useRouter();
  const [items, setItems] = useState<Item[]>([]);
  const [loading, setLoading] = useState(false);

  async function run() {
    setLoading(true);
    try {
      const res = await api<{ items: Item[] }>("/discover", { method: "POST" });
      setItems(res.items || []);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "خطا");
    } finally {
      setLoading(false);
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

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">کشف</h1>
          <p className="text-sm text-muted-foreground">
            پیشنهاد هوشمند بر اساس تاریخچه شما
          </p>
        </div>
        <Button onClick={run} disabled={loading}>
          <Sparkles />
          {loading ? "…" : "پیشنهاد بگیر"}
        </Button>
      </div>
      {items.map((item, i) => (
        <Card key={i}>
          <CardContent className="flex items-center justify-between gap-3 py-4">
            <div>
              <p className="font-medium">{item.title}</p>
              <p className="text-sm text-muted-foreground">{item.artist}</p>
            </div>
            <Button size="sm" onClick={() => download(item)}>
              دانلود
            </Button>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
