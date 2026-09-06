// frontend/app/projects/[projectId]/scenes/page.tsx
'use client';

import { useMemo, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { ArrowRight, CheckCircle2, FileText, Sparkles } from 'lucide-react';
import { AppShell } from '@/components/app-shell';
import { OpportunityBadge } from '@/components/opportunity-badge';
import { ProjectLoading, ProjectNotFound } from '@/components/project-state';
import { useProject } from '@/lib/use-project';
import type { AnalyzedScene, ReferenceOpportunity } from '@/lib/types';

type Filter = 'all' | ReferenceOpportunity;

const FILTERS: { id: Filter; label: string }[] = [
    { id: 'all', label: 'All Scenes' },
    { id: 'strong reference opportunity', label: 'Strong Opportunities' },
    { id: 'possible reference opportunity', label: 'Possible Opportunities' },
    { id: 'no reference needed', label: 'No Reference Needed' },
];

// Present all analyzed scenes with opportunity filters and clear detail navigation.
export default function ScenesPage() {
    const { projectId } = useParams<{ projectId: string }>();
    const { snapshot, loading } = useProject(projectId);
    const [filter, setFilter] = useState<Filter>('all');

    const filteredScenes = useMemo(() => {
        if (!snapshot) return [];
        return snapshot.result.scenes.filter((item) => filter === 'all' || item.analysis.reference_opportunity === filter);
    }, [filter, snapshot]);

    if (loading) return <AppShell><ProjectLoading /></AppShell>;
    if (!snapshot) return <AppShell><ProjectNotFound /></AppShell>;

    const counts = countOpportunities(snapshot.result.scenes);
    const totalOpportunities = counts.strong + counts.possible;

    return (
        <AppShell>
            <section className="mx-auto max-w-7xl px-5 py-8 sm:px-8 sm:py-10">
                <header className="flex flex-col gap-5 border-b border-slate-200 pb-7 sm:flex-row sm:items-center sm:justify-between">
                    <div className="flex items-start gap-4">
                        <span className="grid size-11 shrink-0 place-items-center rounded-full bg-emerald-100 text-emerald-700"><CheckCircle2 size={24} /></span>
                        <div>
                            <p className="text-xs font-bold uppercase tracking-[0.14em] text-emerald-700">Analysis complete</p>
                            <h1 className="mt-1 text-2xl font-bold tracking-[-0.03em] text-slate-950 sm:text-3xl">{snapshot.result.filename}</h1>
                            <p className="mt-1.5 text-sm text-slate-500">Found {snapshot.result.scenes.length} {snapshot.result.scenes.length === 1 ? 'scene' : 'scenes'} · {totalOpportunities} potential reference {totalOpportunities === 1 ? 'opportunity' : 'opportunities'}</p>
                        </div>
                    </div>
                    <Link href="/" className="inline-flex items-center justify-center gap-2 rounded-lg border border-slate-200 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 shadow-sm hover:border-slate-300 hover:text-slate-950"><FileText size={16} /> Analyze another script</Link>
                </header>

                {totalOpportunities === 0 && (
                    <div className="mt-6 flex items-start gap-3 rounded-xl border border-blue-200 bg-blue-50 p-4 text-sm text-blue-900">
                        <Sparkles className="mt-0.5 shrink-0" size={17} />
                        <p>Gemini found no scenes that require a cultural reference. The complete scene analysis remains available below.</p>
                    </div>
                )}

                <div className="mt-7 grid gap-6 lg:grid-cols-[230px_1fr]">
                    <aside>
                        <div className="rounded-2xl border border-slate-200 bg-white p-3 shadow-sm">
                            {FILTERS.map((item) => {
                                const count = item.id === 'all' ? snapshot.result.scenes.length : counts[opportunityKey(item.id)];
                                return (
                                    <button key={item.id} type="button" onClick={() => setFilter(item.id)} className={`flex w-full items-center justify-between rounded-xl px-3 py-3 text-left text-xs font-semibold transition ${filter === item.id ? 'bg-violet-100 text-violet-800' : 'text-slate-600 hover:bg-slate-50 hover:text-slate-950'}`}>
                                        <span>{item.label}</span>
                                        <span className={`rounded-full px-2 py-0.5 text-[10px] ${filter === item.id ? 'bg-white/70' : 'bg-slate-100'}`}>{count}</span>
                                    </button>
                                );
                            })}
                        </div>
                    </aside>

                    <div className="space-y-3">
                        {filteredScenes.length ? filteredScenes.map((item) => (
                            <SceneCard key={item.scene.scene_id} projectId={projectId} item={item} index={snapshot.result.scenes.findIndex((candidate) => candidate.scene.scene_id === item.scene.scene_id)} />
                        )) : (
                            <div className="rounded-2xl border border-dashed border-slate-300 bg-white px-6 py-14 text-center">
                                <p className="font-semibold text-slate-800">No scenes in this filter</p>
                                <p className="mt-1 text-sm text-slate-500">Choose another opportunity level to continue.</p>
                            </div>
                        )}
                    </div>
                </div>
            </section>
        </AppShell>
    );
}

// Render one compact scene result with genuine Gemini-derived fields.
function SceneCard({ projectId, item, index }: { projectId: string; item: AnalyzedScene; index: number }) {
    const tags = Array.from(new Set([...item.analysis.tone, ...item.analysis.emotions])).slice(0, 4);
    return (
        <Link href={`/projects/${projectId}/scenes/${item.scene.scene_id}`} className="group block rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition hover:-translate-y-0.5 hover:border-violet-200 hover:shadow-md">
            <div className="flex gap-4">
                <span className="mt-0.5 flex h-7 min-w-8 items-center justify-center rounded-lg bg-slate-100 px-2 text-[11px] font-bold text-slate-500">{String(index + 1).padStart(2, '0')}</span>
                <div className="min-w-0 flex-1">
                    <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                        <h2 className="truncate text-sm font-bold text-slate-950 sm:text-base">{item.scene.heading}</h2>
                        <OpportunityBadge opportunity={item.analysis.reference_opportunity} />
                    </div>
                    <p className="mt-2 line-clamp-2 text-sm leading-6 text-slate-600">{sceneExcerpt(item)}</p>
                    <div className="mt-3 flex flex-wrap items-center gap-2">
                        {tags.map((tag) => <span key={tag} className="rounded-md bg-slate-100 px-2 py-1 text-[10px] font-semibold capitalize text-slate-600">{tag}</span>)}
                        <span className="ml-auto hidden items-center gap-1 text-xs font-semibold text-violet-700 group-hover:flex">Open analysis <ArrowRight size={14} /></span>
                    </div>
                </div>
            </div>
        </Link>
    );
}

// Build a readable excerpt without changing the preserved raw screenplay text.
function sceneExcerpt(item: AnalyzedScene): string {
    const body = item.scene.raw_text
        .split('\n')
        .slice(1)
        .map((line) => line.trim())
        .filter(Boolean)
        .join(' ');
    return body || item.analysis.primary_beat;
}

// Aggregate backend classifications for summary and filter counts.
function countOpportunities(scenes: AnalyzedScene[]) {
    return scenes.reduce(
        (counts, item) => {
            counts[opportunityKey(item.analysis.reference_opportunity)] += 1;
            return counts;
        },
        { strong: 0, possible: 0, none: 0 },
    );
}

// Convert public labels into stable count keys used only by the view.
function opportunityKey(opportunity: Filter): 'strong' | 'possible' | 'none' {
    if (opportunity === 'strong reference opportunity') return 'strong';
    if (opportunity === 'possible reference opportunity') return 'possible';
    return 'none';
}
