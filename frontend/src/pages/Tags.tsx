import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, GitMerge, Pencil, Plus, Trash2 } from "lucide-react";
import { type FormEvent, useMemo, useState } from "react";

import Card from "../components/Card.tsx";
import { ListEmpty } from "../components/ui/Illustrations.tsx";
import { Chip, ConfirmDialog, Drawer, EmptyState, ErrorState, Field, ReadOnlyBanner, SkeletonText, TextInput, useToast } from "../components/ui/index.ts";
import { api, type Tag, TAG_CATEGORY_LABELS, type TagCategory } from "../lib/api.ts";
import { useAuth } from "../lib/auth.tsx";
import { AdminTabs } from "./admin/AdminTabs.tsx";

const CATEGORIES = Object.keys(TAG_CATEGORY_LABELS) as TagCategory[];

/** One screen for both roles. Members read and propose; admins edit, approve, merge and delete. */
export default function Tags({ admin = false }: { admin?: boolean }) {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const canEdit = admin && isAdmin;
  const qc = useQueryClient();
  const { toast } = useToast();
  const tags = useQuery({ queryKey: ["tags"], queryFn: () => api.get<Tag[]>("/api/tags") });
  const [editing, setEditing] = useState<Tag | "new" | null>(null);
  const [merging, setMerging] = useState<Tag | null>(null);
  const [deleting, setDeleting] = useState<Tag | null>(null);
  const [filter, setFilter] = useState("");

  const refresh = () => qc.invalidateQueries({ queryKey: ["tags"] });

  const grouped = useMemo(() => {
    const needle = filter.trim().toLowerCase();
    const list = (tags.data ?? []).filter(
      (t) => !needle || t.name.toLowerCase().includes(needle) || t.synonyms.some((s) => s.toLowerCase().includes(needle)),
    );
    return CATEGORIES.map((c) => ({ category: c, tags: list.filter((t) => t.category === c) })).filter((g) => g.tags.length);
  }, [tags.data, filter]);

  const proposed = (tags.data ?? []).filter((t) => t.status === "proposed");

  const approve = useMutation({
    mutationFn: (t: Tag) => api.patch<Tag>(`/api/tags/${t.id}`, { status: "approved" }),
    onSuccess: (t) => {
      void refresh();
      toast({ title: `“${t.name}” approved` });
    },
  });
  const del = useMutation({
    mutationFn: (t: Tag) => api.delete(`/api/tags/${t.id}`),
    onSuccess: () => {
      void refresh();
      setDeleting(null);
      toast({ title: "Tag removed" });
    },
    onError: (err) => toast({ title: "Couldn't remove the tag", text: err.message, tone: "loss" }),
  });

  return (
    <div className="flex flex-col gap-4 laptop:gap-6">
      {canEdit ? <AdminTabs /> : null}
      {!canEdit ? <ReadOnlyBanner owner="the team" what="shared tag list" /> : null}

      {canEdit && proposed.length ? (
        <Card title="Proposed by members" subtitle="Approve, edit or remove">
          <ul className="divide-y divide-border">
            {proposed.map((t) => (
              <li key={t.id} className="flex flex-wrap items-center gap-2 py-2">
                <span className="text-body">{t.name}</span>
                <span className="text-label text-muted">{TAG_CATEGORY_LABELS[t.category]}</span>
                {t.synonyms.map((s) => (
                  <Chip key={s}>{s}</Chip>
                ))}
                <span className="ml-auto flex gap-1">
                  <button type="button" className="btn btn-secondary" onClick={() => approve.mutate(t)}>
                    <Check aria-hidden className="size-4" /> Approve
                  </button>
                  <button type="button" className="btn btn-ghost size-11 px-0" aria-label={`Edit ${t.name}`} onClick={() => setEditing(t)}>
                    <Pencil aria-hidden className="size-4" />
                  </button>
                  <button type="button" className="btn btn-ghost size-11 px-0" aria-label={`Remove ${t.name}`} onClick={() => setDeleting(t)}>
                    <Trash2 aria-hidden className="size-4" />
                  </button>
                </span>
              </li>
            ))}
          </ul>
        </Card>
      ) : null}

      <Card
        title="Tag vocabulary"
        subtitle="One shared ICT/SMC list. Synonyms resolve to the same tag: FVG = fair value gap = f.v.g"
        controls={
          <div className="flex items-center gap-2">
            <input
              type="search"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              placeholder="Filter"
              aria-label="Filter tags"
              className="input hidden w-40 tablet:block"
            />
            <button type="button" className="btn btn-primary" onClick={() => setEditing("new")}>
              <Plus aria-hidden className="size-4" />
              <span className="hidden tablet:inline">{canEdit ? "New tag" : "Propose a tag"}</span>
              <span className="tablet:hidden">{canEdit ? "New" : "Propose"}</span>
            </button>
          </div>
        }
      >
        <input
          type="search"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Filter"
          aria-label="Filter tags"
          className="input mb-4 tablet:hidden"
        />
        {tags.isPending ? (
          <SkeletonText lines={6} />
        ) : tags.isError ? (
          <ErrorState text={tags.error.message} onRetry={() => tags.refetch()} />
        ) : grouped.length === 0 ? (
          <EmptyState illustration={<ListEmpty />} title={filter ? `Nothing matches “${filter}”` : "No tags yet"} text={filter ? "Try a synonym." : "Propose the first one."} />
        ) : (
          <div className="grid gap-6 laptop:grid-cols-2 large:grid-cols-3">
            {grouped.map(({ category, tags: list }) => (
              <section key={category} aria-label={TAG_CATEGORY_LABELS[category]} className="min-w-0">
                <h3 className="mb-2 text-label text-muted">{TAG_CATEGORY_LABELS[category]}</h3>
                <ul className="divide-y divide-border rounded-panel border border-border">
                  {list.map((t) => (
                    <li key={t.id} className="flex min-h-11 items-center gap-2 px-3 py-2">
                      <div className="min-w-0 flex-1">
                        <p className="break-words text-body">
                          {t.name}
                          {t.status === "proposed" ? <span className="ml-2 text-label text-muted">proposed</span> : null}
                        </p>
                        {t.synonyms.length ? <p className="truncate text-label text-muted">{t.synonyms.join(" · ")}</p> : null}
                      </div>
                      {canEdit ? (
                        <>
                          <button type="button" className="btn btn-ghost size-11 px-0" aria-label={`Edit ${t.name}`} onClick={() => setEditing(t)}>
                            <Pencil aria-hidden className="size-4" />
                          </button>
                          <button type="button" className="btn btn-ghost size-11 px-0" aria-label={`Merge ${t.name} into another tag`} onClick={() => setMerging(t)}>
                            <GitMerge aria-hidden className="size-4" />
                          </button>
                        </>
                      ) : null}
                    </li>
                  ))}
                </ul>
              </section>
            ))}
          </div>
        )}
      </Card>

      <TagDrawer tag={editing} canEdit={canEdit} onClose={() => setEditing(null)} />
      <MergeDrawer source={merging} all={tags.data ?? []} onClose={() => setMerging(null)} />
      <ConfirmDialog
        open={!!deleting}
        onOpenChange={(o) => !o && setDeleting(null)}
        title={`Remove “${deleting?.name}”?`}
        text="Trades keep the tag, but nobody can pick it any more. Merging is usually better."
        confirmLabel="Remove tag"
        danger
        busy={del.isPending}
        onConfirm={() => deleting && del.mutate(deleting)}
      />
    </div>
  );
}

function TagDrawer({ tag, canEdit, onClose }: { tag: Tag | "new" | null; canEdit: boolean; onClose: () => void }) {
  const qc = useQueryClient();
  const { toast } = useToast();
  const isNew = tag === "new";
  const existing = tag && tag !== "new" ? tag : null;
  const [name, setName] = useState("");
  const [category, setCategory] = useState<TagCategory>("other");
  const [synonyms, setSynonyms] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [key, setKey] = useState<string | number | null>(null);
  const current = existing ? existing.id : isNew ? "new" : null;
  if (current !== key) {
    setKey(current);
    setName(existing?.name ?? "");
    setCategory(existing?.category ?? "other");
    setSynonyms(existing?.synonyms.join(", ") ?? "");
    setError(null);
  }
  const save = useMutation({
    mutationFn: () => {
      const body = { name: name.trim(), category, synonyms: synonyms.split(",").map((s) => s.trim()).filter(Boolean) };
      return existing ? api.patch<Tag>(`/api/tags/${existing.id}`, body) : api.post<Tag>("/api/tags", body);
    },
    onSuccess: (t) => {
      void qc.invalidateQueries({ queryKey: ["tags"] });
      toast({ title: t.status === "proposed" ? `“${t.name}” proposed` : `“${t.name}” saved`, text: t.status === "proposed" ? "The admin will approve it." : undefined });
      onClose();
    },
    onError: (err) => setError(err.message),
  });
  return (
    <Drawer
      open={tag !== null}
      onOpenChange={(o) => !o && onClose()}
      title={existing ? `Edit ${existing.name}` : canEdit ? "New tag" : "Propose a tag"}
      description={canEdit ? undefined : "Members propose; the admin approves."}
    >
      <form
        className="flex flex-col gap-4"
        onSubmit={(e: FormEvent) => {
          e.preventDefault();
          save.mutate();
        }}
      >
        <Field label="Name" error={error}>
          {(p) => <TextInput {...p} required maxLength={80} value={name} onChange={(e) => setName(e.target.value)} />}
        </Field>
        <Field label="Category">
          {(p) => (
            <select {...p} className="input" value={category} onChange={(e) => setCategory(e.target.value as TagCategory)}>
              {CATEGORIES.map((c) => (
                <option key={c} value={c}>
                  {TAG_CATEGORY_LABELS[c]}
                </option>
              ))}
            </select>
          )}
        </Field>
        <Field label="Synonyms" help="Comma-separated. Case and punctuation don't matter.">
          {(p) => <TextInput {...p} value={synonyms} onChange={(e) => setSynonyms(e.target.value)} placeholder="fair value gap, f.v.g" />}
        </Field>
        <button type="submit" className="btn btn-primary" disabled={save.isPending || !name.trim()}>
          {existing ? "Save changes" : canEdit ? "Create tag" : "Propose tag"}
        </button>
      </form>
    </Drawer>
  );
}

function MergeDrawer({ source, all, onClose }: { source: Tag | null; all: Tag[]; onClose: () => void }) {
  const qc = useQueryClient();
  const { toast } = useToast();
  const [into, setInto] = useState<number | "">("");
  const merge = useMutation({
    mutationFn: () => api.post<Tag>(`/api/tags/${source!.id}/merge`, { into_id: into }),
    onSuccess: (t) => {
      void qc.invalidateQueries({ queryKey: ["tags"] });
      toast({ title: `Merged into “${t.name}”`, text: `“${source?.name}” is now a synonym.` });
      setInto("");
      onClose();
    },
    onError: (err) => toast({ title: "Couldn't merge", text: err.message, tone: "loss" }),
  });
  return (
    <Drawer open={!!source} onOpenChange={(o) => !o && onClose()} title={`Merge “${source?.name}”`} description="Its name and synonyms become synonyms of the tag you pick.">
      <div className="flex flex-col gap-4">
        <Field label="Into">
          {(p) => (
            <select {...p} className="input" value={into} onChange={(e) => setInto(Number(e.target.value))}>
              <option value="">Pick a tag</option>
              {all
                .filter((t) => t.id !== source?.id)
                .map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name} · {TAG_CATEGORY_LABELS[t.category]}
                  </option>
                ))}
            </select>
          )}
        </Field>
        <button type="button" className="btn btn-primary" disabled={into === "" || merge.isPending} onClick={() => merge.mutate()}>
          <GitMerge aria-hidden className="size-4" />
          Merge
        </button>
      </div>
    </Drawer>
  );
}
