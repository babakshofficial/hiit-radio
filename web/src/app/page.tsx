"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Download, Loader2, Search, X } from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";

type Job = {
  id: string;
  status: string;
  progress: number;
  message: string;
  title?: string;
  artist?: string;
  artwork_url?: string;
  file_url?: string;
  error?: string;
  kind?: string;
  tracks_total?: number;
  tracks_done?: number;
  track_results?: Array<{
    title?: string;
    artist?: string;
    status?: string;
    file_url?: string;
  }>;
};

export default function HomePage() {
  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState(false);
  const [job, setJob] = useState<Job | null>(null);

  useEffect(() => {
    if (!job || !["queued", "running"].includes(job.status)) return;
    const t = setInterval(async () => {
      try {
        const j = await api<Job>(`/jobs/${job.id}`);
        setJob(j);
        if (j.status === "done") toast.success("آماده دانلود");
        if (j.status === "error") toast.error(j.message || "خطا");
        if (j.status === "cancelled") toast.message("لغو شد");
      } catch (e) {
        console.error(e);
      }
    }, 1200);
    return () => clearInterval(t);
  }, [job]);

  async function start(kind: "download" | "playlist") {
    if (!query.trim()) return;
    setBusy(true);
    try {
      const path = kind === "playlist" ? "/jobs/playlist" : "/jobs/download";
      const j = await api<Job>(path, {
        method: "POST",
        body: JSON.stringify({ query: query.trim() }),
      });
      setJob(j);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "خطا");
    } finally {
      setBusy(false);
    }
  }

  async function cancel() {
    if (!job) return;
    try {
      const j = await api<Job>(`/jobs/${job.id}/cancel`, { method: "POST" });
      setJob(j);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "خطا");
    }
  }

  const active = job && ["queued", "running"].includes(job.status);

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">دانلود آهنگ</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          لینک Apple Music / Spotify یا نام آهنگ را وارد کنید
        </p>
      </div>

      <Card>
        <CardContent className="flex flex-col gap-3 pt-6">
          <div className="flex gap-2">
            <Input
              dir="ltr"
              className="text-left"
              placeholder="https://music.apple.com/... or song name"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && start("download")}
            />
            <Button disabled={busy || !!active} onClick={() => start("download")}>
              {busy ? <Loader2 className="animate-spin" /> : <Search />}
              جستجو
            </Button>
          </div>
          <Button
            variant="outline"
            disabled={busy || !!active}
            onClick={() => start("playlist")}
          >
            دانلود آلبوم / پلی‌لیست
          </Button>
        </CardContent>
      </Card>

      {job && (
        <Card>
          <CardHeader className="flex flex-row items-start justify-between gap-3 space-y-0">
            <div className="flex gap-3">
              {job.artwork_url ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={job.artwork_url}
                  alt=""
                  className="size-16 rounded-lg object-cover"
                />
              ) : null}
              <div>
                <CardTitle className="text-base">
                  {job.title || "در حال پردازش…"}
                </CardTitle>
                <p className="text-sm text-muted-foreground">{job.artist}</p>
                <Badge variant="outline" className="mt-2">
                  {job.status}
                </Badge>
              </div>
            </div>
            {active && (
              <Button variant="ghost" size="icon-sm" onClick={cancel}>
                <X />
              </Button>
            )}
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            <Progress value={job.progress || 0} />
            <p className="text-sm text-muted-foreground">{job.message}</p>
            {job.file_url && (
              <Button render={<a href={job.file_url} download />}>
                <Download />
                دانلود MP3
              </Button>
            )}
            {job.track_results && job.track_results.length > 0 && (
              <ul className="divide-y rounded-lg border">
                {job.track_results.map((t, i) => (
                  <li
                    key={i}
                    className="flex items-center justify-between gap-2 px-3 py-2 text-sm"
                  >
                    <span>
                      {t.title} — {t.artist}
                      <span className="ms-2 text-muted-foreground">{t.status}</span>
                    </span>
                    {t.file_url && (
                      <a className="text-primary underline" href={t.file_url} download>
                        MP3
                      </a>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
