// frontend/app/projects/[projectId]/scenes/[sceneId]/page.tsx
'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';
import {
    ArrowLeft,
    Brain,
    Clapperboard,
    Eye,
    Lightbulb,
    MessageCircleQuestion,
    Search,
    Target,
    Users,
} from 'lucide-react';
import { AppShell } from '@/components/app-shell';
import { OpportunityBadge } from '@/components/opportunity-badge';
import { ProjectLoading, ProjectNotFound } from '@/components/project-state';
import { SceneSidebar } from '@/components/scene-sidebar';
import { SceneTabs } from '@/components/scene-tabs';
import { useProject } from '@/lib/use-project';

// Translate every structured Gemini field into a scannable filmmaking workspace.
export default function SceneDetailPage() {
    const { projectId, sceneId } = useParams<{ projectId: string; sceneId: string }>();
    const { snapshot, loading } = useProject(projectId);

    if (loading) return <AppShell><ProjectLoading /></AppShell>;
    if (!snapshot) return <AppShell><ProjectNotFound /></AppShell>;
    const item = snapshot.result.scenes.find((candidate) => candidate.scene.scene_id === sceneId);
    if (!item) return <AppShell><ProjectNotFound /></AppShell>;

    const { scene, analysis } = item;
    return (
        <AppShell>
            <div className="lg:flex">
                <SceneSidebar projectId={projectId} scenes={snapshot.result.scenes} activeSceneId={sceneId} />
                <section className="min-w-0 flex-1 px-5 py-7 sm:px-8 lg:px-10">
                    <div className="mx-auto max-w-5xl">
                        <Link href={`/projects/${projectId}/scenes`} className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-violet-700"><ArrowLeft size={14} /> Back to all scenes</Link>
                        <header className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                            <div>
                                <p className="text-xs font-bold uppercase tracking-[0.12em] text-violet-700">{scene.scene_id.split('_')[1]}</p>
                                <h1 className="mt-1 text-2xl font-bold tracking-[-0.03em] text-slate-950">{scene.heading}</h1>
                                <p className="mt-1.5 text-sm text-slate-500">{analysis.scene_type} · {scene.location}{scene.time_of_day ? ` · ${scene.time_of_day}` : ''}</p>
                            </div>
                            <OpportunityBadge opportunity={analysis.reference_opportunity} />
                        </header>
                        <div className="mt-6"><SceneTabs projectId={projectId} sceneId={sceneId} active="analysis" queryCount={analysis.reference_queries.length} /></div>

                        <div className="mt-7 grid gap-5 xl:grid-cols-[1.35fr_0.65fr]">
                            <div className="space-y-5">
                                <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
                                    <p className="text-xs font-bold uppercase tracking-[0.12em] text-slate-400">Primary beat</p>
                                    <p className="mt-2 text-lg font-semibold leading-7 text-slate-950">{analysis.primary_beat}</p>
                                    <div className="mt-5 flex flex-wrap gap-2">
                                        {Array.from(new Set([...analysis.tone, ...analysis.emotions])).map((tag) => <Tag key={tag}>{tag}</Tag>)}
                                    </div>
                                </section>

                                <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
                                    <div className="flex items-center gap-2 text-slate-950"><Clapperboard size={18} className="text-violet-600" /><h2 className="font-bold">Scene text</h2></div>
                                    <pre className="mt-4 max-h-80 overflow-auto whitespace-pre-wrap rounded-xl bg-slate-950 p-5 font-mono text-xs leading-6 text-slate-200">{scene.raw_text}</pre>
                                </section>

                                <div className="grid gap-5 md:grid-cols-2">
                                    <InsightCard icon={Target} title="Mechanism"><p>{analysis.comedic_or_dramatic_mechanism}</p></InsightCard>
                                    <InsightCard icon={Users} title="Character intentions">
                                        <ul className="space-y-3">{analysis.character_intentions.map((entry, index) => <li key={`${entry.character}-${index}`}><strong className="text-slate-900">{entry.character}</strong><span className="mt-0.5 block">{entry.intention}</span></li>)}</ul>
                                    </InsightCard>
                                    <InsightCard icon={Brain} title="Important actions"><BulletList values={analysis.important_actions} /></InsightCard>
                                    <InsightCard icon={Eye} title="Visual characteristics"><BulletList values={analysis.visual_characteristics} /></InsightCard>
                                    <InsightCard icon={Lightbulb} title="Cultural concepts"><BulletList values={analysis.cultural_concepts} /></InsightCard>
                                    <InsightCard icon={Users} title="Characters"><div className="flex flex-wrap gap-2">{analysis.characters.map((character) => <Tag key={character}>{character}</Tag>)}</div></InsightCard>
                                </div>
                            </div>

                            <aside className="space-y-5">
                                <section className="rounded-2xl border border-violet-200 bg-gradient-to-b from-violet-50 to-white p-5 shadow-sm">
                                    <div className="flex items-center justify-between"><span className="text-xs font-bold uppercase tracking-[0.12em] text-violet-700">Reference score</span><span className="text-2xl font-bold text-violet-800">{analysis.reference_opportunity_score}</span></div>
                                    <div className="mt-3 h-2 overflow-hidden rounded-full bg-violet-100"><span className="block h-full rounded-full bg-violet-600" style={{ width: `${analysis.reference_opportunity_score}%` }} /></div>
                                    <p className="mt-4 text-sm leading-6 text-slate-700">{analysis.reference_opportunity_reason}</p>
                                </section>

                                <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                                    <div className="flex items-center gap-2"><Search size={17} className="text-violet-600" /><h2 className="text-sm font-bold text-slate-950">Prepared for live reference search</h2></div>
                                    {analysis.reference_queries.length ? (
                                        <ol className="mt-4 space-y-2">{analysis.reference_queries.map((query, index) => <li key={`${query}-${index}`} className="flex gap-2 rounded-lg bg-slate-50 px-3 py-2.5 text-xs leading-5 text-slate-700"><span className="font-bold text-violet-600">{index + 1}</span>{query}</li>)}</ol>
                                    ) : (
                                        <p className="mt-3 text-sm leading-6 text-slate-500">No search queries were generated because this scene does not need a cultural reference.</p>
                                    )}
                                    {analysis.reference_queries.length > 0 && <Link href={`/projects/${projectId}/scenes/${sceneId}/references`} className="mt-4 inline-flex w-full justify-center rounded-lg bg-violet-700 px-4 py-2.5 text-xs font-semibold text-white hover:bg-violet-800">Find Cultural References</Link>}
                                </section>

                                <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                                    <div className="flex items-center gap-2"><MessageCircleQuestion size={17} className="text-violet-600" /><h2 className="text-sm font-bold">Why this matters</h2></div>
                                    <p className="mt-3 text-sm leading-6 text-slate-600">Parallel retrieves real source pages, Gemini evaluates their fit, and application code calculates the final ranking.</p>
                                </section>
                            </aside>
                        </div>
                    </div>
                </section>
            </div>
        </AppShell>
    );
}

// Render a titled structured-analysis card with a consistent icon cue.
function InsightCard({ icon: Icon, title, children }: { icon: typeof Target; title: string; children: React.ReactNode }) {
    return (
        <section className="rounded-2xl border border-slate-200 bg-white p-5 text-sm leading-6 text-slate-600 shadow-sm">
            <div className="mb-3 flex items-center gap-2 text-slate-950"><Icon size={17} className="text-violet-600" /><h2 className="font-bold">{title}</h2></div>
            {children}
        </section>
    );
}

// Render short categorical values as restrained workspace tags.
function Tag({ children }: { children: React.ReactNode }) {
    return <span className="rounded-md bg-violet-50 px-2.5 py-1 text-[11px] font-semibold capitalize text-violet-700 ring-1 ring-inset ring-violet-100">{children}</span>;
}

// Render array fields as concise bullet points rather than raw JSON.
function BulletList({ values }: { values: string[] }) {
    return <ul className="space-y-2">{values.map((value, index) => <li key={`${value}-${index}`} className="flex gap-2"><span className="mt-2 size-1.5 shrink-0 rounded-full bg-violet-500" />{value}</li>)}</ul>;
}
