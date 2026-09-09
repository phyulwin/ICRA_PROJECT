// frontend/components/directing-workspace.tsx
'use client';

import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';
import { useParams } from 'next/navigation';
import { ArrowLeft, ArrowUpRight, Check, LoaderCircle, RefreshCw, Save } from 'lucide-react';
import { AppShell } from './app-shell';
import { OpportunityBadge } from './opportunity-badge';
import { ProjectLoading, ProjectNotFound } from './project-state';
import { SceneSidebar } from './scene-sidebar';
import { SceneTabs } from './scene-tabs';
import { generateDirectingGuidance, getLatestDirectingGuidance, saveDirectingBoard } from '@/lib/api';
import type { DirectingGuidance, DirectingGuidanceResult } from '@/lib/types';
import { useProject } from '@/lib/use-project';

// Present persisted Gemini guidance and allow a server-backed directing board save.
export function DirectingWorkspace() {
    const { projectId, sceneId } = useParams<{ projectId: string; sceneId: string }>();
    const { snapshot, loading: projectLoading } = useProject(projectId);
    const [result, setResult] = useState<DirectingGuidanceResult | null>(null);
    const [loading, setLoading] = useState(true);
    const [regenerating, setRegenerating] = useState(false);
    const [saving, setSaving] = useState(false);
    const [saved, setSaved] = useState(false);
    const [title, setTitle] = useState('');
    const [notes, setNotes] = useState('');
    const [error, setError] = useState<string | null>(null);
    const item = useMemo(() => snapshot?.result.scenes.find((entry) => entry.scene.scene_id === sceneId) ?? null, [sceneId, snapshot]);

    // Restore the newest Firestore guidance draft after every page load.
    useEffect(() => {
        void getLatestDirectingGuidance(projectId, sceneId)
            .then((value) => {
                setResult(value);
                setTitle(`${value.guidance.reference_title} directing board`);
            })
            .catch((reason) => setError(reason instanceof Error ? reason.message : 'Directing guidance could not be loaded.'))
            .finally(() => setLoading(false));
    }, [projectId, sceneId]);

    // Re-run Gemini against the same real, server-persisted reference.
    async function regenerate() {
        if (!result) return;
        setRegenerating(true);
        setError(null);
        setSaved(false);
        try {
            const value = await generateDirectingGuidance(projectId, sceneId, result.search_id, result.guidance.reference_id);
            setResult(value);
        } catch (reason) {
            setError(reason instanceof Error ? reason.message : 'Guidance could not be regenerated.');
        } finally {
            setRegenerating(false);
        }
    }

    // Save only the server-owned structured draft to Firestore.
    async function saveBoard() {
        if (!result) return;
        setSaving(true);
        setError(null);
        try {
            await saveDirectingBoard(projectId, sceneId, result.guidance_id, title, notes);
            setSaved(true);
        } catch (reason) {
            setError(reason instanceof Error ? reason.message : 'Directing board could not be saved.');
        } finally {
            setSaving(false);
        }
    }

    if (projectLoading) return <AppShell><ProjectLoading /></AppShell>;
    if (!snapshot || !item) return <AppShell><ProjectNotFound /></AppShell>;

    return <AppShell><div className="lg:flex"><SceneSidebar projectId={projectId} scenes={snapshot.result.scenes} activeSceneId={sceneId} /><section className="min-w-0 flex-1 px-5 py-7 sm:px-8 lg:px-10"><div className="mx-auto max-w-6xl"><Link href={`/projects/${projectId}/scenes/${sceneId}/references`} className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-violet-700"><ArrowLeft size={14} /> Back to references</Link><header className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between"><div><p className="text-xs font-bold uppercase tracking-[0.12em] text-violet-700">{item.scene.scene_id.split('_')[1]}</p><h1 className="mt-1 text-2xl font-bold tracking-[-0.03em] text-slate-950">{item.scene.heading}</h1></div><OpportunityBadge opportunity={item.analysis.reference_opportunity} /></header><div className="mt-6"><SceneTabs projectId={projectId} sceneId={sceneId} active="directing" queryCount={item.analysis.reference_queries.length} /></div>{loading && <div className="flex items-center gap-2 py-16 text-sm text-slate-500"><LoaderCircle className="animate-spin" size={18} /> Loading directing guidance</div>}{error && <p className="mt-6 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">{error}</p>}{!loading && !result && <section className="mt-7 rounded-2xl border border-dashed border-slate-300 bg-white p-10 text-center"><h2 className="font-bold text-slate-950">Select a reference first</h2><p className="mt-2 text-sm text-slate-500">Use a verified reference to create grounded directing guidance.</p><Link href={`/projects/${projectId}/scenes/${sceneId}/references`} className="mt-5 inline-flex rounded-lg bg-violet-700 px-4 py-2.5 text-sm font-semibold text-white">Open references</Link></section>}{result && <GuidanceView result={result} title={title} notes={notes} setTitle={setTitle} setNotes={setNotes} regenerate={regenerate} saveBoard={saveBoard} regenerating={regenerating} saving={saving} saved={saved} />}</div></section></div></AppShell>;
}

// Render every structured guidance category while retaining source attribution.
function GuidanceView({ result, title, notes, setTitle, setNotes, regenerate, saveBoard, regenerating, saving, saved }: { result: DirectingGuidanceResult; title: string; notes: string; setTitle: (value: string) => void; setNotes: (value: string) => void; regenerate: () => void; saveBoard: () => void; regenerating: boolean; saving: boolean; saved: boolean }) {
    const guidance = result.guidance;
    const sections: Array<[string, keyof DirectingGuidance]> = [['Performance', 'performance'], ['Facial expression', 'facial_expression'], ['Body language', 'body_language'], ['Blocking', 'blocking'], ['Camera', 'camera'], ['Framing', 'framing'], ['Shot sequence', 'shot_sequence'], ['Pacing and timing', 'timing'], ['Editing', 'editing'], ['Sound', 'sound'], ['Visual style', 'visual_style'], ['What to borrow', 'what_to_borrow'], ['What not to copy', 'what_not_to_copy']];
    return <><section className="mt-7 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm"><div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between"><div><p className="text-xs font-bold uppercase tracking-[0.12em] text-violet-700">Selected reference</p><h2 className="mt-2 text-xl font-bold text-slate-950">{guidance.reference_title}</h2><a href={result.reference_url} target="_blank" rel="noopener noreferrer" className="mt-2 inline-flex items-center gap-1 text-sm font-semibold text-violet-700">{result.source_domain} <ArrowUpRight size={14} /></a></div><button type="button" onClick={regenerate} disabled={regenerating} className="inline-flex items-center justify-center gap-2 rounded-lg border border-slate-200 px-4 py-2.5 text-sm font-semibold text-slate-700 disabled:bg-slate-100">{regenerating ? <LoaderCircle className="animate-spin" size={16} /> : <RefreshCw size={16} />} Regenerate</button></div><div className="mt-6 rounded-xl bg-violet-50 p-5"><h3 className="font-bold text-violet-950">Creative intent</h3><p className="mt-2 text-sm leading-6 text-violet-900">{guidance.creative_intent}</p></div><div className="mt-6 grid gap-4 md:grid-cols-2">{sections.map(([label, key]) => <GuidanceSection key={key} label={label} items={guidance[key] as string[]} />)}</div><div className="mt-5 rounded-xl bg-slate-950 p-5 text-white"><h3 className="font-bold">Director note</h3><p className="mt-2 text-sm leading-6 text-slate-200">{guidance.concise_director_note}</p></div></section><section className="mt-6 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm"><h2 className="font-bold text-slate-950">Save directing board</h2><div className="mt-4 grid gap-4"><label className="text-xs font-semibold text-slate-600">Board title<input value={title} onChange={(event) => setTitle(event.target.value)} className="mt-2 w-full rounded-lg border border-slate-200 px-3 py-2.5 text-sm" /></label><label className="text-xs font-semibold text-slate-600">Production notes<textarea value={notes} onChange={(event) => setNotes(event.target.value)} rows={4} className="mt-2 w-full rounded-lg border border-slate-200 px-3 py-2.5 text-sm" /></label></div><button type="button" onClick={saveBoard} disabled={saving || !title.trim()} className="mt-4 inline-flex items-center gap-2 rounded-lg bg-violet-700 px-4 py-2.5 text-sm font-semibold text-white disabled:bg-slate-300">{saving ? <LoaderCircle className="animate-spin" size={16} /> : saved ? <Check size={16} /> : <Save size={16} />}{saving ? 'Saving...' : saved ? 'Board saved' : 'Save Directing Board'}</button></section></>;
}

// Display one structured guidance list inside a collapsed disclosure panel.
function GuidanceSection({ label, items }: { label: string; items: string[] }) {
    if (items.length === 0) return null;
    return <details className="group self-start rounded-xl border border-slate-200 bg-white"><summary className="flex cursor-pointer list-none items-center justify-between p-5 font-bold text-slate-950"><span>{label}</span><span><span className="group-open:hidden">▼</span><span className="hidden group-open:inline">▲</span></span></summary><ul className="space-y-2 border-t border-slate-100 px-5 pb-5 pt-4 text-sm leading-6 text-slate-600">{items.map((item) => <li key={item} className="flex gap-2"><span className="mt-2 size-1.5 shrink-0 rounded-full bg-violet-500" />{item}</li>)}</ul></details>;
}
