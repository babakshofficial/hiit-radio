"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

type Item = { title?: string; artist?: string; cnt?: number };

export default function ChartsPage() {
  const router = useRouter();
  const [period, setPeriod] = useState("week");
  const [items, setItems] = useState<Item[]>([]);

  useEffect(() => {
    (async () => {
      try {
        const res = await api<{ items: Item[] }>(`/top?period=${period}&limit=30`);
        setItems(res.items || []);
      } catch (e) {
        toast.error(e instanceof Error ? e.message : "خطا");
      }
    })();
  }, [period]);

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
      <h1 className="text-2xl font-semibold">چارت</h1>
      <Tabs value={period} onValueChange={setPeriod}>
        <TabsList>
          <TabsTrigger value="day">روز</TabsTrigger>
          <TabsTrigger value="week">هفته</TabsTrigger>
          <TabsTrigger value="all">همه</TabsTrigger>
        </TabsList>
        <TabsContent value={period} className="mt-4 flex flex-col gap-2">
          {items.map((item, i) => (
            <Card key={`${item.title}-${i}`}>
              <CardContent className="flex items-center justify-between gap-3 py-4">
                <div className="flex items-center gap-3">
                  <Badge variant="secondary">{i + 1}</Badge>
                  <div>
                    <p className="font-medium">{item.title}</p>
                    <p className="text-sm text-muted-foreground">
                      {item.artist} · {item.cnt} دانلود
                    </p>
                  </div>
                </div>
                <Button size="sm" onClick={() => download(item)}>
                  دانلود
                </Button>
              </CardContent>
            </Card>
          ))}
          {!items.length && (
            <p className="text-sm text-muted-foreground">داده‌ای نیست</p>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
