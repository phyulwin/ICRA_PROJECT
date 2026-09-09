// frontend/components/reference-workspace.tsx
'use client';

import Link from 'next/link';
import { useEffect, useMemo, useRef, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import {
    ArrowLeft,
    ArrowUpRight,
    ImageOff,
    LoaderCircle,
    Search,
    SlidersHorizontal,
    Square,
} from 'lucide-react';
import { AppShell } from './app-shell';
import { OpportunityBadge } from './opportunity-badge';
import { ProjectLoading, ProjectNotFound } from './project-state';
import { SceneSidebar } from './scene-sidebar';
import { SceneTabs } from './scene-tabs';
import { cancelCulturalReferenceSearch, findCulturalReferences, generateDirectingGuidance, getSearch, listLibraryReferences, listRefinements, listSearches, saveLibraryReference, updateSelection } from '@/lib/api';
import type {
    CulturalReferenceType,
    MatchFor,
    RankedReference,
    ReferenceEra,
    ReferenceSearchPreferences,
    ReferenceSearchResponse,
    ReferenceType,
    SourcePlatform,
    RefinementRecord,
    SearchRecord,
} from '@/lib/types';
import { useProject } from '@/lib/use-project';

type SearchStatus = 'idle' | 'searching' | 'success' | 'cancelled' | 'error';

const DEFAULT_PREFERENCES: ReferenceSearchPreferences = {
    reference_type: 'all',
    era: 'any',
    match_for: 'best_overall',
    recognition: 50,
    max_results: 5,
};

const PLATFORM_LABELS: Record<SourcePlatform, string> = {
    tiktok: 'TikTok',
    instagram: 'Instagram',
    youtube: 'YouTube',
    giphy: 'GIPHY',
    tenor: 'Tenor',
    meme: 'Meme',
    reddit: 'Reddit',
    film_tv: 'Film / TV',
    web: 'Web',
};

const TYPE_LABELS: Record<CulturalReferenceType, string> = {
    reaction_meme: 'Reaction meme',
    viral_video: 'Viral video',
    tiktok: 'TikTok',
    instagram_reel: 'Instagram Reel',
    gif: 'GIF',
    film_tv_moment: 'Film / TV',
    anime_moment: 'Anime',
    informational_article: 'Article',
    other: 'Cultural moment',
};


// Activate the Phase 3 scene workspace without exposing external-service credentials.
export function ReferenceWorkspace() {
    const { projectId, sceneId } = useParams<{ projectId: string; sceneId: string }>();
    const router = useRouter();
    const { snapshot, loading } = useProject(projectId);
    const [preferences, setPreferences] = useState(DEFAULT_PREFERENCES);
    const [status, setStatus] = useState<SearchStatus>('idle');
    const [result, setResult] = useState<ReferenceSearchResponse | null>(null);
    const [selectedSearchId, setSelectedSearchId] = useState<string | null>(null);
    const [searchHistory, setSearchHistory] = useState<SearchRecord[]>([]);
    const [refinements, setRefinements] = useState<RefinementRecord[]>([]);
    const [selectedId, setSelectedId] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [savedReferenceIds, setSavedReferenceIds] = useState<Set<string>>(new Set());
    const [savingReferenceId, setSavingReferenceId] = useState<string | null>(null);
    const [directingReferenceId, setDirectingReferenceId] = useState<string | null>(null);
    const requestController = useRef<AbortController | null>(null);
    const activeRequestId = useRef<string | null>(null);

    const item = useMemo(
        () => snapshot?.result.scenes.find(
            (candidate) => candidate.scene.scene_id === sceneId,
        ) ?? null,
        [sceneId, snapshot],
    );

    // Restore the latest durable search after backend hydration.
    useEffect(() => {
        let cancelled = false;
        void Promise.all([listSearches(projectId, sceneId), listRefinements(projectId, sceneId)])
            .then(async ([searches, refinementHistory]) => {
                setSearchHistory(searches);
                setRefinements(refinementHistory);
                const latest = searches[0];
                if (!latest) return;
                const detail = await getSearch(projectId, sceneId, latest.search_id);
                if (cancelled) return;
                setSelectedSearchId(detail.search_id);
                setResult({
                    scene_id: detail.scene_id,
                    references: detail.references,
                    raw_candidate_count: detail.raw_candidate_count,
                    rejected_candidate_count: 0,
                    extracted_candidate_count: 0,
                    searched_queries: detail.queries,
                    failed_queries: detail.failed_queries,
                    warnings: detail.warnings,
                    partial_success: detail.status === 'partial_success',
                    retry_count: detail.retry_count,
                    search_id: detail.search_id,
                    search_plan: detail.search_plan,
                });
                setSelectedId(detail.chosen_reference_id ?? detail.references[0]?.reference.id ?? null);
                setStatus('success');
            })
            .catch(() => undefined);
        return () => { cancelled = true; };
    }, [projectId, sceneId]);

    // Cancel any in-flight fetch when the scene changes or the workspace unmounts.
    useEffect(() => () => {
        requestController.current?.abort();
        requestController.current = null;
        if (activeRequestId.current) {
            void cancelCulturalReferenceSearch(activeRequestId.current);
            activeRequestId.current = null;
        }
    }, [projectId, sceneId]);

    // Restore saved-state badges from the backend Library after a browser refresh.
    useEffect(() => {
        void listLibraryReferences(projectId)
            .then((items) => setSavedReferenceIds(new Set(items.map((entry) => entry.reference_id))))
            .catch(() => undefined);
    }, [projectId]);

    // Call FastAPI once and present honest progressive stages while the pipeline runs.
    async function runSearch() {
        if (!item || item.analysis.reference_queries.length === 0) return;

        if (activeRequestId.current) {
            void cancelCulturalReferenceSearch(activeRequestId.current);
        }
        requestController.current?.abort();
        const controller = new AbortController();
        const requestId = crypto.randomUUID();
        requestController.current = controller;
        activeRequestId.current = requestId;
        setError(null);
        setStatus('searching');

        try {
            const response = await findCulturalReferences(
                projectId,
                item.scene,
                item.analysis,
                preferences,
                controller.signal,
                requestId,
            );
            if (controller.signal.aborted) return;
            setResult(response);
            setSelectedSearchId(response.search_id);
            setSelectedId(response.references[0]?.reference.id ?? null);
            setStatus('success');
        } catch (reason) {
            if (controller.signal.aborted) {
                if (requestController.current === controller) {
                    setStatus('cancelled');
                }
                return;
            }
            setError(
                reason instanceof Error
                    ? reason.message
                    : 'Reference search could not be completed.',
            );
            setStatus('error');
        } finally {
            if (requestController.current === controller) {
                requestController.current = null;
                activeRequestId.current = null;
            }
        }
    }

    // Abort the network request immediately while retaining the last good result.
    function cancelSearch() {
        const controller = requestController.current;
        if (!controller) return;
        const requestId = activeRequestId.current;
        requestController.current = null;
        activeRequestId.current = null;
        if (requestId) {
            void cancelCulturalReferenceSearch(requestId);
        }
        controller.abort();
        setError(null);
        setStatus('cancelled');
    }

    async function chooseReference(referenceId: string | null) {
        if (!selectedSearchId) return;
        try {
            await updateSelection(projectId, sceneId, selectedSearchId, referenceId);
            setSelectedId(referenceId);
        } catch (reason) {
            setError(reason instanceof Error ? reason.message : 'Selection could not be saved.');
        }
    }

    // Persist the reference through FastAPI so Firestore remains the source of truth.
    async function saveReference(referenceId: string) {
        if (!selectedSearchId) {
            setError('Run or restore a persisted search before saving this reference.');
            return;
        }
        setSavingReferenceId(referenceId);
        setError(null);
        try {
            await saveLibraryReference(projectId, sceneId, selectedSearchId, referenceId);
            setSavedReferenceIds((current) => new Set(current).add(referenceId));
        } catch (reason) {
            setError(reason instanceof Error ? reason.message : 'Reference could not be saved.');
        } finally {
            setSavingReferenceId(null);
        }
    }

    // Select a real reference, generate structured guidance, and open Directing Notes.
    async function useForDirecting(referenceId: string) {
        if (!selectedSearchId) {
            setError('Run or restore a persisted search before generating guidance.');
            return;
        }
        setDirectingReferenceId(referenceId);
        setError(null);
        try {
            await updateSelection(projectId, sceneId, selectedSearchId, referenceId);
            setSelectedId(referenceId);
            await generateDirectingGuidance(projectId, sceneId, selectedSearchId, referenceId);
            router.push(`/projects/${projectId}/scenes/${sceneId}/directing-notes`);
        } catch (reason) {
            setError(reason instanceof Error ? reason.message : 'Directing guidance could not be generated.');
        } finally {
            setDirectingReferenceId(null);
        }
    }

    async function openSearch(searchId: string) {
        try {
            const detail = await getSearch(projectId, sceneId, searchId);
            setSelectedSearchId(detail.search_id);
            setResult({
                scene_id: detail.scene_id,
                references: detail.references,
                raw_candidate_count: detail.raw_candidate_count,
                rejected_candidate_count: 0,
                extracted_candidate_count: 0,
                searched_queries: detail.queries,
                failed_queries: detail.failed_queries,
                warnings: detail.warnings,
                partial_success: detail.status === 'partial_success',
                retry_count: detail.retry_count,
                search_id: detail.search_id,
                search_plan: detail.search_plan,
            });
            setSelectedId(detail.chosen_reference_id ?? detail.references[0]?.reference.id ?? null);
            setStatus('success');
        } catch (reason) {
            setError(reason instanceof Error ? reason.message : 'Search history could not be loaded.');
        }
    }

    if (loading) return <AppShell><ProjectLoading /></AppShell>;
    if (!snapshot || !item) return <AppShell><ProjectNotFound /></AppShell>;

    const isSearching = status === 'searching';
    const canSearch = item.analysis.reference_queries.length > 0;

    return (
        <AppShell>
            <div className="lg:flex">
                <SceneSidebar projectId={projectId} scenes={snapshot.result.scenes} activeSceneId={sceneId} />
                <section className="min-w-0 flex-1 px-5 py-7 sm:px-8 lg:px-10">
                    <div className="mx-auto max-w-6xl">
                        <Link href={`/projects/${projectId}/scenes`} className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-violet-700"><ArrowLeft size={14} /> Back to all scenes</Link>
                        <header className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                            <div>
                                <p className="text-xs font-bold uppercase tracking-[0.12em] text-violet-700">{item.scene.scene_id.split('_')[1]}</p>
                                <h1 className="mt-1 text-2xl font-bold tracking-[-0.03em] text-slate-950">{item.scene.heading}</h1>
                            </div>
                            <OpportunityBadge opportunity={item.analysis.reference_opportunity} />
                        </header>
                        <div className="mt-6"><SceneTabs projectId={projectId} sceneId={sceneId} active="references" queryCount={item.analysis.reference_queries.length} /></div>

                        <section className="mt-7 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
                            <div className="flex items-center gap-2"><SlidersHorizontal size={18} className="text-violet-600" /><h2 className="font-bold text-slate-950">Search preferences</h2></div>
                            <fieldset disabled={isSearching} className="mt-5 grid gap-4 disabled:opacity-60 sm:grid-cols-2 xl:grid-cols-5">
                                <SelectControl label="Reference type" value={preferences.reference_type} onChange={(value) => setPreferences({ ...preferences, reference_type: value as ReferenceType })} options={[['all', 'All'], ['tiktok_short_form', 'TikTok / Short-form'], ['instagram_reels', 'Instagram / Reels'], ['memes', 'Memes'], ['reaction_gifs', 'Reaction GIFs']]} />
                                <SelectControl label="Era" value={preferences.era} onChange={(value) => setPreferences({ ...preferences, era: value as ReferenceEra })} options={[['any', 'Any'], ['trending_current', 'Trending / Current'], ['2020_present', '2020–Present'], ['2015_2019', '2015–2019'], ['2010_2014', '2010–2014'], ['2000s', '2000s'], ['pre_2000', 'Pre-2000']]} />
                                <SelectControl label="Match priority" value={preferences.match_for} onChange={(value) => setPreferences({ ...preferences, match_for: value as MatchFor })} options={[['best_overall', 'Best Overall'], ['performance', 'Performance / Acting'], ['facial_expression', 'Facial Expression'], ['situation', 'Situation'], ['visual_composition', 'Visual Composition'], ['body_language', 'Body Language'], ['comedic_timing', 'Comedic Timing'], ['emotional_beat', 'Emotional Beat'], ['camera_framing', 'Camera / Framing']]} />
                                <label className="text-xs font-semibold text-slate-600">Recognition · {preferences.recognition}<input className="mt-3 w-full accent-violet-700" type="range" min="0" max="100" value={preferences.recognition} onChange={(event) => setPreferences({ ...preferences, recognition: Number(event.target.value) })} /><span className="mt-1 flex justify-between text-[10px] font-medium text-slate-400"><span>Niche</span><span>Iconic</span></span></label>
                                <SelectControl label="Results" value={String(preferences.max_results)} onChange={(value) => setPreferences({ ...preferences, max_results: Number(value) })} options={[["3", "Top 3"], ["4", "Top 4"], ["5", "Top 5"]]} />
                            </fieldset>
                            <div className="mt-6 flex flex-wrap items-center gap-4">
                                <button type="button" onClick={isSearching ? cancelSearch : runSearch} disabled={!canSearch} className={`inline-flex w-full items-center justify-center gap-2 rounded-lg px-5 py-3 text-sm font-semibold text-white shadow-sm disabled:cursor-not-allowed disabled:bg-slate-300 sm:w-auto ${isSearching ? 'bg-rose-600 hover:bg-rose-700' : 'bg-violet-700 hover:bg-violet-800'}`}>
                                    {isSearching ? <Square size={15} fill="currentColor" /> : <Search size={16} />}
                                    {isSearching ? 'Cancel Search' : result ? 'Find more references' : 'Find Cultural References'}
                                </button>
                                {isSearching && <span role="status" className="inline-flex items-center gap-2 text-sm font-semibold text-slate-600"><LoaderCircle className="animate-spin text-violet-600" size={18} aria-hidden="true" />Finding References...</span>}
                            </div>
                            {item.analysis.reference_queries.length === 0 && <p className="mt-3 text-sm text-slate-500">Gemini did not identify a reference opportunity for this scene.</p>}
                        </section>

                        <fieldset disabled={isSearching} className="contents">
                        {searchHistory.length > 0 && <section className="mt-6 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"><h2 className="font-bold text-slate-950">Search history</h2><div className="mt-4 flex gap-2 overflow-x-auto pb-1">{searchHistory.map((search, index) => <button key={search.search_id} type="button" onClick={() => void openSearch(search.search_id)} className={`min-w-44 rounded-lg border px-3 py-2 text-left text-xs disabled:cursor-not-allowed disabled:opacity-50 ${search.search_id === selectedSearchId ? 'border-violet-300 bg-violet-50 text-violet-900' : 'border-slate-200 text-slate-600 hover:border-violet-200'}`}><span className="block font-bold">Search {searchHistory.length - index}</span><span className="mt-1 block">{new Date(search.created_at).toLocaleString()}</span><span className="mt-1 block">{search.retained_candidate_count} results · {search.preferences.reference_type}</span></button>)}</div></section>}
                        {refinements.length > 0 && <section className="mt-6 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"><h2 className="font-bold text-slate-950">Refinement history</h2><div className="mt-3 space-y-2">{refinements.map((refinement) => <div key={refinement.refinement_id} className="rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-600"><span className="font-semibold text-slate-900">{refinement.user_text}</span><span className="ml-2">{new Date(refinement.created_at).toLocaleString()}</span></div>)}</div></section>}

                        {status === 'cancelled' && <section role="status" className="mt-6 rounded-2xl border border-amber-200 bg-amber-50 p-5"><p className="font-semibold text-amber-900">Search cancelled</p><p className="mt-1 text-sm text-amber-700">Your previous references remain available. You can start another search now.</p></section>}
                        {error && <section className="mt-6 rounded-2xl border border-rose-200 bg-rose-50 p-5"><p className="font-semibold text-rose-900">Reference search failed</p><p className="mt-2 text-sm text-rose-700">{error}</p></section>}
                        {result && <ReferenceResults result={result} selectedId={selectedId} onSelect={setSelectedId} onChoose={chooseReference} onSave={saveReference} onDirect={useForDirecting} savedReferenceIds={savedReferenceIds} savingReferenceId={savingReferenceId} directingReferenceId={directingReferenceId} />}
                        </fieldset>
                    </div>
                </section>
            </div>
        </AppShell>
    );
}


// Render one reusable labeled select without coupling values to display labels.
function SelectControl({ label, value, onChange, options }: { label: string; value: string; onChange: (value: string) => void; options: string[][] }) {
    return <label className="text-xs font-semibold text-slate-600">{label}<select value={value} onChange={(event) => onChange(event.target.value)} className="mt-2 w-full rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-800 outline-none focus:border-violet-400">{options.map(([optionValue, optionLabel]) => <option key={optionValue} value={optionValue}>{optionLabel}</option>)}</select></label>;
}


// Present ranked references while retaining a direct source link on every card.
function ReferenceResults({ result, selectedId, onSelect, onChoose, onSave, onDirect, savedReferenceIds, savingReferenceId, directingReferenceId }: { result: ReferenceSearchResponse; selectedId: string | null; onSelect: (id: string) => void; onChoose: (id: string | null) => void; onSave: (id: string) => void; onDirect: (id: string) => void; savedReferenceIds: Set<string>; savingReferenceId: string | null; directingReferenceId: string | null }) {
    if (result.references.length === 0) return <section className="mt-6 rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-sm"><ImageOff size={28} className="mx-auto text-slate-400" /><h2 className="mt-3 font-bold text-slate-950">No traceable references found</h2><p className="mt-2 text-sm text-slate-500">Adjust the filters or try a broader reference type.</p></section>;
    return <section className="mt-6">{result.search_plan && <details className="mb-5 rounded-xl border border-violet-100 bg-violet-50 p-4"><summary className="cursor-pointer text-sm font-bold text-violet-950">Search strategy</summary><p className="mt-3 text-sm text-violet-900">{result.search_plan.creative_target}</p><p className="mt-2 text-xs text-violet-700">{result.search_plan.queries.length} diverse queries · {result.search_plan.platform_targets.join(', ') || 'cross-platform'} · excludes {result.search_plan.negative_intents.join(', ')}</p></details>}<div className="flex flex-wrap items-end justify-between gap-3"><h2 className="text-xl font-bold text-slate-950">References</h2>{result.partial_success && <span className="rounded-full bg-amber-50 px-3 py-1 text-xs font-semibold text-amber-700">Partial search success</span>}</div><div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-3">{result.references.map((ranked) => <ReferenceCard key={ranked.reference.id} ranked={ranked} selected={ranked.reference.id === selectedId} onSelect={() => onSelect(ranked.reference.id)} onChoose={() => onChoose(ranked.reference.id)} onClear={() => onChoose(null)} onSave={() => onSave(ranked.reference.id)} onDirect={() => onDirect(ranked.reference.id)} saved={savedReferenceIds.has(ranked.reference.id)} saving={savingReferenceId === ranked.reference.id} directing={directingReferenceId === ranked.reference.id} />)}</div></section>;
}


// Render provider facts and use a neutral placeholder when Parallel has no image.
function ReferenceCard({ ranked, selected, onSelect, onChoose, onClear, onSave, onDirect, saved, saving, directing }: { ranked: RankedReference; selected: boolean; onSelect: () => void; onChoose: () => void; onClear: () => void; onSave: () => void; onDirect: () => void; saved: boolean; saving: boolean; directing: boolean }) {
    const { reference, assessment, overall_score: score } = ranked;
    const platform = PLATFORM_LABELS[reference.source_platform ?? 'web'];
    const artifactType = TYPE_LABELS[assessment.cultural_reference_type ?? 'other'];
    return <article className={`overflow-hidden rounded-2xl border bg-white shadow-sm transition ${selected ? 'border-violet-400 ring-2 ring-violet-100' : 'border-slate-200'}`}>
        {reference.image_url ? (
            // Parallel Search does not currently supply images; render only legitimate future URLs.
            // eslint-disable-next-line @next/next/no-img-element
            <img src={reference.image_url} alt={`Preview for ${reference.title}`} className="h-36 w-full object-cover" />
        ) : <div className="grid h-36 place-items-center bg-gradient-to-br from-slate-100 to-violet-50 text-slate-400"><ImageOff size={30} /><span className="sr-only">No source image available</span></div>}
        <div className="p-5"><div className="flex items-start justify-between gap-3"><div className="flex flex-wrap gap-1.5"><span className="rounded-full bg-slate-900 px-2.5 py-1 text-[11px] font-bold text-white">{platform}</span><span className="rounded-full bg-violet-50 px-2.5 py-1 text-[11px] font-semibold text-violet-700">{artifactType}</span></div><span className="rounded-full bg-violet-100 px-2.5 py-1 text-xs font-bold text-violet-800">MATCH {score}%</span></div><h3 className="mt-2 line-clamp-2 font-bold leading-6 text-slate-950">{reference.title}</h3><p className="mt-2 line-clamp-3 text-sm leading-6 text-slate-600">{reference.snippet || 'Parallel returned no excerpt for this source.'}</p><p className="mt-3 text-xs font-semibold text-slate-700">Best for: {assessment.best_for.join(' + ')}</p><details className="group mt-3 border-t border-slate-100 pt-3"><summary className="flex cursor-pointer list-none items-center justify-between text-xs font-semibold text-slate-700"><span>Why it matches</span><span><span className="group-open:hidden">▼</span><span className="hidden group-open:inline">▲</span></span></summary><p className="mt-3 text-xs leading-5 text-slate-500">{assessment.match_reason}</p>{assessment.useful_directing_elements.length > 0 && <ul className="mt-3 list-disc pl-4 text-xs leading-5 text-slate-500">{assessment.useful_directing_elements.map((element) => <li key={element}>{element}</li>)}</ul>}<p className="mt-2 text-[10px] text-slate-400">Recognition is an inferred ranking signal.</p></details><div className="mt-4 flex items-center justify-between gap-3"><button type="button" onClick={onSelect} className="text-xs font-bold text-violet-700 hover:text-violet-900">View details</button><a href={reference.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-xs font-semibold text-slate-500 hover:text-violet-700">Source <ArrowUpRight size={13} /></a></div><div className="mt-4 grid grid-cols-2 gap-2"><button type="button" onClick={onSave} disabled={saved || saving} className="rounded-lg border border-violet-200 px-3 py-2 text-xs font-bold text-violet-700 disabled:bg-violet-50">{saving ? 'Saving...' : saved ? 'Saved' : 'Save to Library'}</button><button type="button" onClick={onDirect} disabled={directing} className="rounded-lg bg-violet-700 px-3 py-2 text-xs font-bold text-white disabled:bg-slate-300">{directing ? 'Generating...' : 'Use for Directing'}</button></div><button type="button" onClick={selected ? onClear : onChoose} className="mt-3 text-xs font-bold text-violet-700 hover:text-violet-900">{selected ? 'Clear selection' : 'Select reference'}</button></div>
    </article>;
}


