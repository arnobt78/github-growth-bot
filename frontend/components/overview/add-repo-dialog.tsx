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
import { useAddRepo } from "@/hooks/use-repos";

export function AddRepoDialog() {
  const [open, setOpen] = useState(false);
  const [owner, setOwner] = useState("");
  const [name, setName] = useState("");
  const addRepo = useAddRepo();

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    addRepo.mutate(
      { owner, name },
      {
        onSuccess: () => {
          toast.success(`Now tracking ${owner}/${name}`);
          setOwner("");
          setName("");
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
      <DialogContent>
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Track a new repo</DialogTitle>
          </DialogHeader>
          <div className="grid gap-4 py-4">
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
