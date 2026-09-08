// frontend/app/library/page.tsx
'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { Archive, ArrowUpRight, FileText, LoaderCircle, Trash2 } from 'lucide-react';
import { AppShell } from '@/components/app-shell';
import { deleteDirectingBoard, deleteLibraryReference, listDirectingBoards, listLibraryReferences, listProjects } from '@/lib/api';
import type { SavedDirectingBoard, SavedReference } from '@/lib/types';

// Load all Library artifacts through FastAPI so Firestore remains the only durable store.
export default function LibraryPage() {
    const [references, setReferences] = useState<SavedReference[]>([]);
    const [boards, setBoards] = useState<SavedDirectingBoard[]>([]);
    const [loading, setLoading] = useState(true);
    const [deletingId, setDeletingId] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);

    // Aggregate project-scoped subcollections without allowing browser Firestore access.
    useEffect(() => {
        void listProjects()
            .then(async (projects) => {
                const projectItems = await Promise.all(projects.map(async (project) => {
                    const [projectReferences, projectBoards] = await Promise.all([listLibraryReferences(project.project_id), listDirectingBoards(project.project_id)]);
                    return { projectReferences, projectBoards };
                }));
                setReferences(projectItems.flatMap((entry) => entry.projectReferences));
                setBoards(projectItems.flatMap((entry) => entry.projectBoards));
            })
            .catch((reason) => setError(reason instanceof Error ? reason.message : 'Library could not be loaded.'))
            .finally(() => setLoading(false));
    }, []);

    // Delete one reference from Firestore and update the visible list after success.
    async function removeReference(item: SavedReference) {
        setDeletingId(item.id);
        setError(null);
        try {
            await deleteLibraryReference(item.project_id, item.id);
            setReferences((current) => current.filter((entry) => entry.id !== item.id));
        } catch (reason) {
            setError(reason instanceof Error ? reason.message : 'Reference could not be deleted.');
        } finally {
            setDeletingId(null);
        }
    }

    // Delete one directing board from Firestore and update the visible list after success.
    async function removeBoard(item: SavedDirectingBoard) {
        setDeletingId(item.id);
        setError(null);
        try {
            await deleteDirectingBoard(item.project_id, item.id);
            setBoards((current) => current.filter((entry) => entry.id !== item.id));
        } catch (reason) {
            setError(reason instanceof Error ? reason.message : 'Directing board could not be deleted.');
        } finally {
            setDeletingId(null);
        }
    }

    const empty = !loading && !error && references.length === 0 && boards.length === 0;
    return <AppShell><section className="mx-auto max-w-6xl px-5 py-8 sm:px-8 sm:py-10"><header className="flex items-end justify-between gap-4 border-b border-slate-200 pb-7"><div><p className="text-xs font-bold uppercase tracking-[0.14em] text-violet-700">Persistent workspace</p><h1 className="mt-1 text-3xl font-bold tracking-[-0.03em] text-slate-950">Library</h1><p className="mt-2 text-sm text-slate-500">Saved references and directing boards, securely loaded from Firestore.</p></div><Link href="/" className="hidden items-center gap-2 rounded-lg bg-violet-700 px-4 py-2.5 text-sm font-semibold text-white hover:bg-violet-800 sm:inline-flex"><FileText size={16} /> New screenplay</Link></header>{loading && <div className="flex items-center gap-2 py-16 text-sm text-slate-500"><LoaderCircle size={18} className="animate-spin" /> Loading Library</div>}{error && <p className="mt-8 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">{error}</p>}{empty && <div className="mt-8 rounded-2xl border border-dashed border-slate-300 bg-white px-6 py-16 text-center"><Archive className="mx-auto text-violet-600" size={30} /><h2 className="mt-4 font-bold text-slate-950">Your Library is empty</h2><p className="mt-2 text-sm text-slate-500">Save a ranked reference or a directing board to keep it here.</p></div>}{references.length > 0 && <LibrarySection title="Saved references"><div className="grid gap-4 md:grid-cols-2">{references.map((item) => <article key={item.id} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"><div className="flex items-start justify-between gap-3"><div><p className="text-xs font-bold uppercase tracking-[0.12em] text-violet-700">{item.scene_heading}</p><h2 className="mt-2 font-bold text-slate-950">{item.reference_title}</h2></div><span className="rounded-full bg-violet-100 px-2.5 py-1 text-xs font-bold text-violet-800">{item.overall_score}%</span></div><p className="mt-3 line-clamp-3 text-sm leading-6 text-slate-600">{item.match_reason || item.description}</p><div className="mt-4 flex items-center justify-between"><a href={item.reference_url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-xs font-semibold text-violet-700">Actual source <ArrowUpRight size={13} /></a><button type="button" onClick={() => void removeReference(item)} disabled={deletingId === item.id} className="inline-flex items-center gap-1 text-xs font-semibold text-rose-700 disabled:text-slate-400">{deletingId === item.id ? <LoaderCircle className="animate-spin" size={14} /> : <Trash2 size={14} />} Delete</button></div></article>)}</div></LibrarySection>}{boards.length > 0 && <LibrarySection title="Directing boards"><div className="grid gap-4 md:grid-cols-2">{boards.map((item) => <article key={item.id} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"><p className="text-xs font-bold uppercase tracking-[0.12em] text-violet-700">{item.scene_heading}</p><h2 className="mt-2 font-bold text-slate-950">{item.user_title}</h2><p className="mt-2 text-sm text-slate-500">Reference: {item.selected_reference.reference.title}</p><p className="mt-3 line-clamp-3 text-sm leading-6 text-slate-600">{item.notes || item.directing_guidance.concise_director_note}</p><div className="mt-4 flex items-center justify-between"><Link href={`/projects/${item.project_id}/scenes/${item.scene_id}/directing-notes`} className="text-xs font-semibold text-violet-700">Open board</Link><button type="button" onClick={() => void removeBoard(item)} disabled={deletingId === item.id} className="inline-flex items-center gap-1 text-xs font-semibold text-rose-700 disabled:text-slate-400">{deletingId === item.id ? <LoaderCircle className="animate-spin" size={14} /> : <Trash2 size={14} />} Delete</button></div></article>)}</div></LibrarySection>}</section></AppShell>;
}

// Keep each Library artifact type visually distinct and easy to scan.
function LibrarySection({ title, children }: { title: string; children: React.ReactNode }) {
    return <section className="mt-8"><h2 className="mb-4 text-xl font-bold text-slate-950">{title}</h2>{children}</section>;
}
