"use client";

import { useState } from "react";
import { Mail } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { SectionHeading } from "@/components/ui/section-heading";
import { useMe, useUpdateMe } from "@/hooks/use-me";

export function NotificationSettingsCard() {
  const { data: me } = useMe();
  const updateMe = useUpdateMe();
  const [value, setValue] = useState(me?.notification_email ?? "");

  const effectiveEmail = me?.notification_email || me?.email || "No email on file";

  const handleSave = () => {
    const trimmed = value.trim();
    updateMe.mutate(
      { notification_email: trimmed || null },
      { onError: () => toast.error("Could not update notification email — try again.") },
    );
  };

  return (
    <div className="space-y-3">
      <SectionHeading icon={Mail} title="Notifications" iconColor="text-amber-500" />
      <Card>
        <CardContent className="space-y-3 py-4">
          <p className="text-sm text-muted-foreground">
            Alert emails currently go to: <span className="font-medium">{effectiveEmail}</span>
          </p>
          <div className="flex items-center gap-2">
            <Input
              type="email"
              value={value}
              onChange={(event) => setValue(event.target.value)}
              placeholder="fallback-email@example.com"
              aria-label="Notification fallback email"
            />
            <Button onClick={handleSave} disabled={updateMe.isPending}>
              Save
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
