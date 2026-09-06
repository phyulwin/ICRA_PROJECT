// frontend/components/future-scene-page.tsx
'use client';

import Link from 'next/link';
import { ArrowLeft, Clock3, Search, WandSparkles } from 'lucide-react';
import { useParams } from 'next/navigation';
import { AppShell } from './app-shell';
import { OpportunityBadge } from './opportunity-badge';
import { ProjectLoading, ProjectNotFound } from './project-state';
import { SceneSidebar } from './scene-sidebar';
import { SceneTabs } from './scene-tabs';
import { useProject } from '@/lib/use-project';

interface FutureScenePageProps {
    active: 'references' | 'directing';
}

// Preserve future scene routes without presenting fabricated Phase 3 content.
export function FutureScenePage({ active }: FutureScenePageProps) {
    const { projectId, sceneId } = useParams<{ projectId: string; sceneId: string }>();
    const { snapshot, loading } = useProject(projectId);

    if (loading) return <AppShell><ProjectLoading /></AppShell>;
    if (!snapshot) return <AppShell><ProjectNotFound /></AppShell>;
    const item = snapshot.result.scenes.find((candidate) => candidate.scene.scene_id === sceneId);
    if (!item) return <AppShell><ProjectNotFound /></AppShell>;

    const references = active === 'references';
    return (
        <AppShell>
            <div className="lg:flex">
                <SceneSidebar projectId={projectId} scenes={snapshot.result.scenes} activeSceneId={sceneId} />
                <section className="min-w-0 flex-1 px-5 py-7 sm:px-8 lg:px-10">
                    <div className="mx-auto max-w-5xl">
                        <Link href={`/projects/${projectId}/scenes`} className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-violet-700"><ArrowLeft size={14} /> Back to all scenes</Link>
                        <header className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                            <div>
                                <p className="text-xs font-bold uppercase tracking-[0.12em] text-violet-700">{item.scene.scene_id.split('_')[1]}</p>
                                <h1 className="mt-1 text-2xl font-bold tracking-[-0.03em] text-slate-950">{item.scene.heading}</h1>
                            </div>
                            <OpportunityBadge opportunity={item.analysis.reference_opportunity} />
                        </header>
                        <div className="mt-6"><SceneTabs projectId={projectId} sceneId={sceneId} active={active} queryCount={item.analysis.reference_queries.length} /></div>

                        <div className="mt-8 grid min-h-96 place-items-center rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-sm">
                            <div className="max-w-lg">
                                <span className="mx-auto grid size-14 place-items-center rounded-2xl bg-violet-100 text-violet-700">
                                    {references ? <Search size={26} /> : <WandSparkles size={26} />}
                                </span>
                                <span className="mt-5 inline-flex items-center gap-1.5 rounded-full bg-slate-100 px-2.5 py-1 text-[11px] font-bold uppercase tracking-[0.1em] text-slate-500"><Clock3 size={12} /> Coming in Phase 3</span>
                                <h2 className="mt-3 text-2xl font-bold tracking-[-0.025em] text-slate-950">{references ? 'Cultural reference results' : 'Directing guidance'}</h2>
                                <p className="mt-3 text-sm leading-6 text-slate-600">
                                    {references
                                        ? 'Parallel-powered internet research and ranked cultural references will appear here. No search has been performed yet.'
                                        : 'Performance, framing, camera, and timing guidance will be created after a cultural reference is selected.'}
                                </p>
                                {references && item.analysis.reference_queries.length > 0 && (
                                    <div className="mt-6 rounded-xl border border-violet-100 bg-violet-50 p-4 text-left">
                                        <p className="text-xs font-bold uppercase tracking-[0.1em] text-violet-700">Ready for search</p>
                                        <p className="mt-2 text-sm text-slate-700">{item.analysis.reference_queries.length} Gemini-generated queries are prepared for the next phase.</p>
                                    </div>
                                )}
                                <Link href={`/projects/${projectId}/scenes/${sceneId}`} className="mt-6 inline-flex rounded-lg bg-violet-700 px-4 py-2.5 text-sm font-semibold text-white hover:bg-violet-800">Return to analysis</Link>
                            </div>
                        </div>
                    </div>
                </section>
            </div>
        </AppShell>
    );
}

