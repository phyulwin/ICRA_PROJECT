// frontend/components/reference-workspace.tsx
'use client';

import Link from 'next/link';
import { useEffect, useMemo, useRef, useState } from 'react';
import { useParams } from 'next/navigation';
import {
    ArrowLeft,
    ArrowUpRight,
    Check,
    Clapperboard,
    ImageOff,
    LoaderCircle,
    Search,
    SlidersHorizontal,
} from 'lucide-react';
import { AppShell } from './app-shell';
import { OpportunityBadge } from './opportunity-badge';
import { ProjectLoading, ProjectNotFound } from './project-state';
import { SceneSidebar } from './scene-sidebar';
import { SceneTabs } from './scene-tabs';
import { findCulturalReferences, getSearch, listRefinements, listSearches, updateSelection } from '@/lib/api';
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

type SearchStatus = 'idle' | 'searching' | 'evaluating' | 'ranking' | 'success' | 'error';

const DEFAULT_PREFERENCES: ReferenceSearchPreferences = {
    reference_type: 'all',
    era: 'any',
    match_for: 'all',
    obscurity: 50,
    max_results: 6,
};

const SCORE_ROWS: Array<[keyof RankedReference['assessment'], string]> = [
    ['visual_similarity', 'Visual / action'],
    ['situational_similarity', 'Situation'],
    ['acting_similarity', 'Performance / body language'],
    ['timing_similarity', 'Comedic timing'],
    ['emotional_similarity', 'Emotion'],
    ['recognizability', 'Internet recognizability'],
];

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
    const { snapshot, loading } = useProject(projectId);
    const [preferences, setPreferences] = useState(DEFAULT_PREFERENCES);
    const [status, setStatus] = useState<SearchStatus>('idle');
    const [result, setResult] = useState<ReferenceSearchResponse | null>(null);
    const [selectedSearchId, setSelectedSearchId] = useState<string | null>(null);
    const [searchHistory, setSearchHistory] = useState<SearchRecord[]>([]);
    const [refinements, setRefinements] = useState<RefinementRecord[]>([]);
    const [selectedId, setSelectedId] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);
    const requestController = useRef<AbortController | null>(null);

    const item = useMemo(
        () => snapshot?.result.scenes.find(
            (candidate) => candidate.scene.scene_id === sceneId,
        ) ?? null,
        [sceneId, snapshot],
    );
    const selected = result?.references.find(
        (candidate) => candidate.reference.id === selectedId,
    ) ?? null;

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
                });
                setSelectedId(detail.chosen_reference_id ?? detail.references[0]?.reference.id ?? null);
                setStatus('success');
            })
            .catch(() => undefined);
        return () => { cancelled = true; };
    }, [projectId, sceneId]);

    // Cancel any in-flight fetch if the user leaves the scene route.
    useEffect(() => () => requestController.current?.abort(), []);

    // Call FastAPI once and present honest progressive stages while the pipeline runs.
    async function runSearch() {
        if (!item || item.analysis.reference_queries.length === 0) return;

        requestController.current?.abort();
        const controller = new AbortController();
        requestController.current = controller;
        setError(null);
        setSelectedId(null);
        setStatus('searching');
        const evaluatingTimer = window.setTimeout(() => setStatus('evaluating'), 900);
        const rankingTimer = window.setTimeout(() => setStatus('ranking'), 2200);

        try {
            const response = await findCulturalReferences(
                projectId,
                item.scene,
                item.analysis,
                preferences,
                controller.signal,
            );
            if (controller.signal.aborted) return;
            setResult(response);
            setSelectedSearchId(response.search_id);
            setSelectedId(response.references[0]?.reference.id ?? null);
            setStatus('success');
        } catch (reason) {
            if (controller.signal.aborted) return;
            setError(
                reason instanceof Error
                    ? reason.message
                    : 'Reference search could not be completed.',
            );
            setStatus('error');
        } finally {
            window.clearTimeout(evaluatingTimer);
            window.clearTimeout(rankingTimer);
        }
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
            });
            setSelectedId(detail.chosen_reference_id ?? detail.references[0]?.reference.id ?? null);
            setStatus('success');
        } catch (reason) {
            setError(reason instanceof Error ? reason.message : 'Search history could not be loaded.');
        }
    }

    if (loading) return <AppShell><ProjectLoading /></AppShell>;
    if (!snapshot || !item) return <AppShell><ProjectNotFound /></AppShell>;

    const isSearching = ['searching', 'evaluating', 'ranking'].includes(status);
    const canSearch = item.analysis.reference_queries.length > 0 && !isSearching;

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
                            <div className="mt-5 grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
                                <SelectControl label="Reference type" value={preferences.reference_type} onChange={(value) => setPreferences({ ...preferences, reference_type: value as ReferenceType })} options={[['all', 'All'], ['memes', 'Memes'], ['internet', 'Internet'], ['film', 'Film / TV'], ['anime', 'Anime'], ['tiktok', 'TikTok']]} />
                                <SelectControl label="Era" value={preferences.era} onChange={(value) => setPreferences({ ...preferences, era: value as ReferenceEra })} options={[['any', 'Any'], ['2000s', '2000s'], ['2010s', '2010s'], ['2020s', '2020s'], ['current', 'Current']]} />
                                <SelectControl label="Match for" value={preferences.match_for} onChange={(value) => setPreferences({ ...preferences, match_for: value as MatchFor })} options={[['all', 'All'], ['acting', 'Acting'], ['situation', 'Situation'], ['visual', 'Visual'], ['timing', 'Timing']]} />
                                <label className="text-xs font-semibold text-slate-600">Obscurity · {preferences.obscurity}<input className="mt-3 w-full accent-violet-700" type="range" min="0" max="100" value={preferences.obscurity} onChange={(event) => setPreferences({ ...preferences, obscurity: Number(event.target.value) })} /><span className="mt-1 flex justify-between text-[10px] font-medium text-slate-400"><span>Mainstream</span><span>Niche</span></span></label>
                                <SelectControl label="Results" value={String(preferences.max_results)} onChange={(value) => setPreferences({ ...preferences, max_results: Number(value) })} options={[["3", "Top 3"], ["4", "Top 4"], ["5", "Top 5"], ["6", "Top 6"]]} />
                            </div>
                            <button type="button" onClick={runSearch} disabled={!canSearch} className="mt-6 inline-flex w-full items-center justify-center gap-2 rounded-lg bg-violet-700 px-5 py-3 text-sm font-semibold text-white shadow-sm hover:bg-violet-800 disabled:cursor-not-allowed disabled:bg-slate-300 sm:w-auto">
                                {isSearching ? <LoaderCircle size={16} className="animate-spin" /> : <Search size={16} />}
                                {result ? 'Find more references' : 'Find Cultural References'}
                            </button>
                            {item.analysis.reference_queries.length === 0 && <p className="mt-3 text-sm text-slate-500">Gemini did not identify a reference opportunity for this scene.</p>}
                        </section>

                        {searchHistory.length > 0 && <section className="mt-6 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"><h2 className="font-bold text-slate-950">Search history</h2><div className="mt-4 flex gap-2 overflow-x-auto pb-1">{searchHistory.map((search, index) => <button key={search.search_id} type="button" onClick={() => void openSearch(search.search_id)} className={`min-w-44 rounded-lg border px-3 py-2 text-left text-xs ${search.search_id === selectedSearchId ? 'border-violet-300 bg-violet-50 text-violet-900' : 'border-slate-200 text-slate-600 hover:border-violet-200'}`}><span className="block font-bold">Search {searchHistory.length - index}</span><span className="mt-1 block">{new Date(search.created_at).toLocaleString()}</span><span className="mt-1 block">{search.retained_candidate_count} results · {search.preferences.reference_type}</span></button>)}</div></section>}
                        {refinements.length > 0 && <section className="mt-6 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"><h2 className="font-bold text-slate-950">Refinement history</h2><div className="mt-3 space-y-2">{refinements.map((refinement) => <div key={refinement.refinement_id} className="rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-600"><span className="font-semibold text-slate-900">{refinement.user_text}</span><span className="ml-2">{new Date(refinement.created_at).toLocaleString()}</span></div>)}</div></section>}

                        {isSearching && <SearchProgress status={status} />}
                        {error && <section className="mt-6 rounded-2xl border border-rose-200 bg-rose-50 p-5"><p className="font-semibold text-rose-900">Reference search failed</p><p className="mt-2 text-sm text-rose-700">{error}</p></section>}
                        {status === 'success' && result && <ReferenceResults result={result} selectedId={selectedId} onSelect={setSelectedId} onChoose={chooseReference} />}
                        {selected && <ReferenceDetail reference={selected} sceneText={item.scene.raw_text} projectId={projectId} sceneId={sceneId} />}
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


// Show the three required backend stages without displaying fabricated interim data.
function SearchProgress({ status }: { status: SearchStatus }) {
    const stages: Array<[SearchStatus, string]> = [['searching', 'Searching the web'], ['evaluating', 'Evaluating references'], ['ranking', 'Ranking matches']];
    const currentIndex = stages.findIndex(([stage]) => stage === status);
    return <section className="mt-6 rounded-2xl border border-violet-100 bg-violet-50 p-6"><h2 className="font-bold text-violet-950">Finding cultural references</h2><div className="mt-5 grid gap-3 sm:grid-cols-3">{stages.map(([stage, label], index) => <div key={stage} className="flex items-center gap-2 rounded-xl bg-white px-4 py-3 text-sm font-semibold text-slate-700 shadow-sm">{index < currentIndex ? <Check size={16} className="text-emerald-600" /> : index === currentIndex ? <LoaderCircle size={16} className="animate-spin text-violet-600" /> : <span className="size-4 rounded-full border border-slate-300" />}{label}</div>)}</div></section>;
}


// Present ranked references while retaining a direct source link on every card.
function ReferenceResults({ result, selectedId, onSelect, onChoose }: { result: ReferenceSearchResponse; selectedId: string | null; onSelect: (id: string) => void; onChoose: (id: string | null) => void }) {
    if (result.references.length === 0) return <section className="mt-6 rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-sm"><ImageOff size={28} className="mx-auto text-slate-400" /><h2 className="mt-3 font-bold text-slate-950">No traceable references found</h2><p className="mt-2 text-sm text-slate-500">Adjust the filters or try a broader reference type.</p></section>;
    return <section className="mt-6"><div className="flex flex-wrap items-end justify-between gap-3"><div><h2 className="text-xl font-bold text-slate-950">Ranked references</h2><p className="mt-1 text-sm text-slate-500">{result.references.length} verified artifacts shown from {result.raw_candidate_count} Parallel candidates; {result.rejected_candidate_count ?? 0} not promoted through the quality gates.</p></div>{result.partial_success && <span className="rounded-full bg-amber-50 px-3 py-1 text-xs font-semibold text-amber-700">Partial search success</span>}</div><div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-3">{result.references.map((ranked) => <ReferenceCard key={ranked.reference.id} ranked={ranked} selected={ranked.reference.id === selectedId} onSelect={() => onSelect(ranked.reference.id)} onChoose={() => onChoose(ranked.reference.id)} onClear={() => onChoose(null)} />)}</div></section>;
}


// Render provider facts and use a neutral placeholder when Parallel has no image.
function ReferenceCard({ ranked, selected, onSelect, onChoose, onClear }: { ranked: RankedReference; selected: boolean; onSelect: () => void; onChoose: () => void; onClear: () => void }) {
    const { reference, assessment, overall_score: score } = ranked;
    const platform = PLATFORM_LABELS[reference.source_platform ?? 'web'];
    const artifactType = TYPE_LABELS[assessment.cultural_reference_type ?? 'other'];
    return <article className={`overflow-hidden rounded-2xl border bg-white shadow-sm transition ${selected ? 'border-violet-400 ring-2 ring-violet-100' : 'border-slate-200'}`}>
        {reference.image_url ? (
            // Parallel Search does not currently supply images; render only legitimate future URLs.
            // eslint-disable-next-line @next/next/no-img-element
            <img src={reference.image_url} alt={`Preview for ${reference.title}`} className="h-36 w-full object-cover" />
        ) : <div className="grid h-36 place-items-center bg-gradient-to-br from-slate-100 to-violet-50 text-slate-400"><ImageOff size={30} /><span className="sr-only">No source image available</span></div>}
        <div className="p-5"><div className="flex items-start justify-between gap-3"><div className="flex flex-wrap gap-1.5"><span className="rounded-full bg-slate-900 px-2.5 py-1 text-[11px] font-bold text-white">{platform}</span><span className="rounded-full bg-violet-50 px-2.5 py-1 text-[11px] font-semibold text-violet-700">{artifactType}</span></div><span className="rounded-full bg-violet-100 px-2.5 py-1 text-xs font-bold text-violet-800">{score}%</span></div><h3 className="mt-2 line-clamp-2 font-bold leading-6 text-slate-950">{reference.title}</h3><p className="mt-2 line-clamp-3 text-sm leading-6 text-slate-600">{reference.snippet || 'Parallel returned no excerpt for this source.'}</p><p className="mt-3 text-xs font-semibold text-slate-700">Why the performance matches</p><p className="mt-1 text-xs leading-5 text-slate-500">{assessment.match_reason}</p><div className="mt-4 flex items-center justify-between gap-3"><button type="button" onClick={onSelect} className="text-xs font-bold text-violet-700 hover:text-violet-900">View match details</button><button type="button" onClick={selected ? onClear : onChoose} className="text-xs font-bold text-violet-700 hover:text-violet-900">{selected ? 'Clear selection' : 'Select reference'}</button><a href={reference.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-xs font-semibold text-slate-500 hover:text-violet-700">Actual source <ArrowUpRight size={13} /></a></div></div>
    </article>;
}


// Show assessment components beside immutable source and original scene context.
function ReferenceDetail({ reference: ranked, sceneText, projectId, sceneId }: { reference: RankedReference; sceneText: string; projectId: string; sceneId: string }) {
    const { reference, assessment } = ranked;
    return <section className="mt-7 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm"><div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between"><div><p className="text-xs font-bold uppercase tracking-[0.12em] text-violet-700">Reference detail</p><h2 className="mt-2 text-xl font-bold text-slate-950">{reference.title}</h2><a href={reference.url} target="_blank" rel="noreferrer" className="mt-2 inline-flex items-center gap-1 text-sm font-semibold text-violet-700 hover:text-violet-900">{reference.source_domain} <ArrowUpRight size={14} /></a></div><span className="text-3xl font-bold text-violet-800">{ranked.overall_score}%</span></div><div className="mt-6 grid gap-6 lg:grid-cols-2"><div><h3 className="text-sm font-bold text-slate-950">Score breakdown</h3><div className="mt-4 space-y-3">{SCORE_ROWS.map(([key, label]) => <ScoreRow key={key} label={label} value={assessment[key] as number} />)}</div></div><div><h3 className="text-sm font-bold text-slate-950">Why the performance matches</h3><p className="mt-3 text-sm leading-6 text-slate-600">{assessment.match_reason}</p><h3 className="mt-5 text-sm font-bold text-slate-950">Artifact evidence</h3><p className="mt-2 text-sm leading-6 text-slate-600">{assessment.artifact_evidence}</p><div className="mt-4 flex flex-wrap gap-2">{assessment.tags.map((tag) => <span key={tag} className="rounded-md bg-violet-50 px-2.5 py-1 text-[11px] font-semibold text-violet-700">{tag}</span>)}</div></div></div><div className="mt-6"><div className="flex items-center gap-2"><Clapperboard size={16} className="text-violet-600" /><h3 className="text-sm font-bold text-slate-950">Original scene context</h3></div><pre className="mt-3 max-h-56 overflow-auto whitespace-pre-wrap rounded-xl bg-slate-950 p-5 font-mono text-xs leading-6 text-slate-200">{sceneText}</pre></div><Link href={`/projects/${projectId}/scenes/${sceneId}/directing-notes`} className="mt-6 inline-flex rounded-lg bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white hover:bg-slate-800">Continue to Directing Guidance</Link></section>;
}


// Render one model-assessed component without conflating it with final weighting.
function ScoreRow({ label, value }: { label: string; value: number }) {
    return <div><div className="flex justify-between text-xs font-semibold text-slate-600"><span>{label}</span><span>{value}</span></div><div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-slate-100"><span className="block h-full rounded-full bg-violet-600" style={{ width: `${value}%` }} /></div></div>;
}
