"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Copy } from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

export default function InvitePage() {
  const [link, setLink] = useState("");
  const [credited, setCredited] = useState(0);
  const [perTopup, setPerTopup] = useState(3);
  const [topupAmount, setTopupAmount] = useState(10);

  useEffect(() => {
    (async () => {
      try {
        const res = await api<{
          link: string;
          credited: number;
          per_topup: number;
          topup_amount: number;
        }>("/invite");
        setLink(res.link);
        setCredited(res.credited);
        setPerTopup(res.per_topup);
        setTopupAmount(res.topup_amount);
      } catch (e) {
        toast.error(e instanceof Error ? e.message : "خطا");
      }
    })();
  }, []);

  function copy() {
    navigator.clipboard.writeText(link);
    toast.success("کپی شد");
  }

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold">دعوت دوستان</h1>
      <Card>
        <CardHeader>
          <CardTitle>لینک دعوت</CardTitle>
          <CardDescription>
            با هر {perTopup} دعوت موفق، +{topupAmount} دانلود همان روز می‌گیرید.
            تا الان {credited} دعوت تایید شده.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex gap-2">
          <Input dir="ltr" className="text-left" readOnly value={link} />
          <Button onClick={copy}>
            <Copy />
            کپی
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
