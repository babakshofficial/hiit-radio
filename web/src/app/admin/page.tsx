"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Label } from "@/components/ui/label";

type UserRow = {
  user_id: string;
  username?: string;
  first_name?: string;
  total_downloads?: number;
};

export default function AdminPage() {
  const { user } = useAuth();
  const [stats, setStats] = useState<{ users: number; downloads: number } | null>(
    null,
  );
  const [users, setUsers] = useState<UserRow[]>([]);
  const [grantUser, setGrantUser] = useState("");
  const [grantDays, setGrantDays] = useState("30");
  const [broadcast, setBroadcast] = useState("");
  const [creds, setCreds] = useState("");

  useEffect(() => {
    if (!user?.is_admin) return;
    (async () => {
      try {
        const [s, u, c] = await Promise.all([
          api<{ users: number; downloads: number }>("/admin/stats"),
          api<{ items: UserRow[] }>("/admin/users?limit=50"),
          api<{ status: string }>("/admin/creds"),
        ]);
        setStats(s);
        setUsers(u.items || []);
        setCreds(c.status || "");
      } catch (e) {
        toast.error(e instanceof Error ? e.message : "Error");
      }
    })();
  }, [user?.is_admin]);

  if (!user?.is_admin) {
    return <p className="text-muted-foreground">Admin only</p>;
  }

  async function doGrant() {
    try {
      await api("/admin/grant", {
        method: "POST",
        body: JSON.stringify({
          user_id: grantUser,
          tier: "premium",
          days: Number(grantDays) || 30,
        }),
      });
      toast.success("Granted");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Error");
    }
  }

  async function doTopup() {
    try {
      await api("/admin/topup", {
        method: "POST",
        body: JSON.stringify({ user_id: grantUser }),
      });
      toast.success("Top-up applied");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Error");
    }
  }

  async function doBroadcast() {
    try {
      const res = await api<{ sent: number; failed: number }>("/admin/broadcast", {
        method: "POST",
        body: JSON.stringify({ message: broadcast }),
      });
      toast.success(`Sent ${res.sent}, failed ${res.failed}`);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Error");
    }
  }

  async function uploadCookies(file: File) {
    const fd = new FormData();
    fd.append("file", file);
    try {
      await api("/admin/cookies", { method: "POST", body: fd });
      toast.success("Cookies uploaded");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Error");
    }
  }

  return (
    <div className="flex flex-col gap-6" dir="ltr">
      <h1 className="text-2xl font-semibold">Admin</h1>
      {stats && (
        <Card>
          <CardHeader>
            <CardTitle>Stats</CardTitle>
          </CardHeader>
          <CardContent>
            Users: {stats.users} · Downloads: {stats.downloads}
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Grant / Top-up</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <Label>User ID</Label>
          <Input value={grantUser} onChange={(e) => setGrantUser(e.target.value)} />
          <Label>Days</Label>
          <Input value={grantDays} onChange={(e) => setGrantDays(e.target.value)} />
          <div className="flex gap-2">
            <Button onClick={doGrant}>Grant premium</Button>
            <Button variant="outline" onClick={doTopup}>
              Day pass
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Broadcast</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <Textarea value={broadcast} onChange={(e) => setBroadcast(e.target.value)} />
          <Button onClick={doBroadcast}>Send</Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Cookies</CardTitle>
        </CardHeader>
        <CardContent>
          <Input
            type="file"
            accept=".txt"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) uploadCookies(f);
            }}
          />
          <pre className="mt-3 max-h-48 overflow-auto whitespace-pre-wrap text-xs text-muted-foreground">
            {creds}
          </pre>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>Users</CardTitle>
          <Button
            variant="outline"
            size="sm"
            render={<a href="/backend/admin/export" />}
            onClick={async (e) => {
              e.preventDefault();
              try {
                const token = localStorage.getItem("hiit_token");
                const res = await fetch("/backend/admin/export", {
                  headers: { Authorization: `Bearer ${token}` },
                });
                const blob = await res.blob();
                const url = URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = url;
                a.download = "users.csv";
                a.click();
              } catch (err) {
                toast.error("Export failed");
              }
            }}
          >
            Export CSV
          </Button>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>ID</TableHead>
                <TableHead>Name</TableHead>
                <TableHead>Downloads</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {users.map((u) => (
                <TableRow key={u.user_id}>
                  <TableCell>{u.user_id}</TableCell>
                  <TableCell>
                    {u.first_name} @{u.username}
                  </TableCell>
                  <TableCell>{u.total_downloads}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
