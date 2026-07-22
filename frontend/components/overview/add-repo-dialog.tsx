"use client";

import { Plus } from "lucide-react";
import { useState, type FormEvent } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { useAddRepo } from "@/hooks/use-repos";

const GITHUB_URL_PATTERN = /^(?:https?:\/\/)?(?:www\.)?github\.com\/([^/\s]+)\/([^/\s#?]+)\/?$/i;

function parseGithubUrl(value: string): { owner: string; name: string } | null {
  const match = value.trim().match(GITHUB_URL_PATTERN);
  if (!match) return null;
  return { owner: match[1], name: match[2].replace(/\.git$/i, "") };
}

export function AddRepoDialog() {
  const [open, setOpen] = useState(false);
  const [owner, setOwner] = useState("");
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const addRepo = useAddRepo();

  function handleUrlChange(value: string) {
    setUrl(value);
    const parsed = parseGithubUrl(value);
    if (parsed) {
      setOwner(parsed.owner);
      setName(parsed.name);
    }
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    addRepo.mutate(
      { owner, name },
      {
        onSuccess: () => {
          toast.success(`Now tracking ${owner}/${name}`);
          setOwner("");
          setName("");
          setUrl("");
          setOpen(false);
        },
        onError: () => toast.error("Could not add that repo — check the owner/name and try again."),
      },
    );
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger render={<Button />}>
        <Plus className="h-4 w-4" aria-hidden="true" />
        Track a repo
      </DialogTrigger>
      <DialogContent className="flex h-[85vh] w-[85vw] max-w-[85vw] flex-col sm:max-w-[85vw]">
        <form onSubmit={handleSubmit} className="flex min-h-0 flex-1 flex-col">
          <DialogHeader>
            <DialogTitle>Track a new repo</DialogTitle>
          </DialogHeader>
          <div className="flex flex-1 flex-col gap-4 overflow-y-auto py-4">
            <div className="grid gap-2">
              <Label htmlFor="url">GitHub URL</Label>
              <Input
                id="url"
                placeholder="https://github.com/owner/repo"
                value={url}
                onChange={(e) => handleUrlChange(e.target.value)}
              />
            </div>
            <div className="flex items-center gap-3">
              <Separator className="flex-1" />
              <span className="text-xs text-muted-foreground">OR</span>
              <Separator className="flex-1" />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="owner">Owner</Label>
              <Input id="owner" value={owner} onChange={(e) => setOwner(e.target.value)} required />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="name">Repo name</Label>
              <Input id="name" value={name} onChange={(e) => setName(e.target.value)} required />
            </div>
          </div>
          <DialogFooter>
            <Button type="submit" disabled={addRepo.isPending}>
              {addRepo.isPending ? "Adding..." : "Add"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
