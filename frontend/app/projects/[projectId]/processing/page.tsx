// frontend/app/projects/[projectId]/processing/page.tsx
'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import {
    BrainCircuit,
    Check,
    Circle,
    FileCheck2,
    Layers3,
    LoaderCircle,
    RotateCcw,
    SearchCheck,
    Sparkles,
} from 'lucide-react';
import { AppShell } from '@/components/app-shell';
import { useAnalysis } from '@/app/providers';

const PROCESSING_STEPS = [
    { label: 'Extracting screenplay', detail: 'Reading text and preserving screenplay structure', icon: FileCheck2 },
    { label: 'Detecting scenes', detail: 'Identifying headings, locations, and characters', icon: Layers3 },
    { label: 'Analyzing scenes with Gemini', detail: 'Understanding tone, intention, beats, and visuals', icon: BrainCircuit },
    { label: 'Finding reference opportunities', detail: 'Scoring cultural-reference potential', icon: SearchCheck },
    { label: 'Preparing results', detail: 'Validating structured analysis and search queries', icon: Sparkles },
];

// Display honest indeterminate progress while the single backend request runs.
export default function ProcessingPage() {
    const params = useParams<{ projectId: string }>();
    const router = useRouter();
    const { status, projectId, fileName, error, result, retryAnalysis } = useAnalysis();
    const [activeStep, setActiveStep] = useState(0);

    // Rotate visual emphasis without marking any backend stage complete prematurely.
    useEffect(() => {
        if (status !== 'processing') return;
        const timer = window.setInterval(() => {
            setActiveStep((current) => (current + 1) % PROCESSING_STEPS.length);
        }, 1800);
        return () => window.clearInterval(timer);
    }, [status]);

    // Move to scene results only after the real API response is validated and stored.
    useEffect(() => {
        if (status !== 'success' || !result || result.projectId !== params.projectId) return;
        const timer = window.setTimeout(() => {
            router.replace(`/projects/${params.projectId}/scenes`);
        }, 700);
        return () => window.clearTimeout(timer);
    }, [params.projectId, result, router, status]);

    const belongsToCurrentJob = projectId === params.projectId;
    const successful = status === 'success' && belongsToCurrentJob;

    // Keep the processing route aligned when a retry creates a fresh project identifier.
    function handleRetry() {
        const retryProjectId = retryAnalysis();
        if (retryProjectId) {
            router.replace(`/projects/${retryProjectId}/processing`);
        }
    }

    return (
        <AppShell>
            <section className="mx-auto max-w-6xl px-5 py-10 sm:px-8 sm:py-16">
                <div className="grid overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-[0_18px_60px_rgba(30,35,60,0.08)] lg:grid-cols-[1.15fr_0.85fr]">
                    <div className="p-6 sm:p-10">
                        <span className="text-xs font-bold uppercase tracking-[0.16em] text-violet-700">Phase 2 · Script intelligence</span>
                        <h1 className="mt-3 text-3xl font-bold tracking-[-0.035em] text-slate-950">
                            {successful ? 'Script Analysis Complete' : status === 'error' && belongsToCurrentJob ? 'Analysis needs attention' : 'Processing Your Script…'}
                        </h1>
                        <p className="mt-3 max-w-xl text-sm leading-6 text-slate-600">
                            {successful
                                ? `Gemini returned ${result?.result.scenes.length ?? 0} validated scene ${result?.result.scenes.length === 1 ? 'analysis' : 'analyses'}.`
                                : 'Your screenplay is being parsed and analyzed securely through the FastAPI backend.'}
                        </p>

                        <div className="mt-8 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
                            <div className="flex items-center gap-3">
                                <span className="grid size-8 place-items-center rounded-full bg-emerald-100 text-emerald-700"><Check size={17} /></span>
                                <div>
                                    <p className="text-sm font-semibold text-slate-900">File ready</p>
                                    <p className="mt-0.5 text-xs text-slate-500">{fileName || 'Screenplay selected in the previous step'}</p>
                                </div>
                            </div>
                        </div>

                        {!belongsToCurrentJob && status === 'idle' ? (
                            <InterruptedState />
                        ) : status === 'error' ? (
                            <ErrorState message={error} onRetry={handleRetry} />
                        ) : (
                            <ol className="mt-4 space-y-2">
                                {PROCESSING_STEPS.map((step, index) => {
                                    const Icon = step.icon;
                                    const active = status === 'processing' && index === activeStep;
                                    return (
                                        <li key={step.label} className={`flex items-center gap-3 rounded-xl border px-4 py-3.5 transition ${successful ? 'border-emerald-100 bg-emerald-50/60' : active ? 'border-violet-200 bg-violet-50' : 'border-transparent bg-white'}`}>
                                            <span className={`grid size-8 shrink-0 place-items-center rounded-full ${successful ? 'bg-emerald-100 text-emerald-700' : active ? 'bg-violet-600 text-white' : 'bg-slate-100 text-slate-400'}`}>
                                                {successful ? <Check size={16} /> : active ? <LoaderCircle className="animate-spin" size={16} /> : <Icon size={15} />}
                                            </span>
                                            <div>
                                                <p className="text-sm font-semibold text-slate-900">{step.label}</p>
                                                <p className="mt-0.5 text-xs text-slate-500">{successful ? 'Completed by the backend' : active ? step.detail : 'Awaiting validated API result'}</p>
                                            </div>
                                        </li>
                                    );
                                })}
                            </ol>
                        )}
                    </div>

                    <div className="relative hidden min-h-[590px] overflow-hidden border-l border-slate-100 bg-gradient-to-br from-slate-50 via-violet-50/70 to-white p-10 lg:grid lg:place-items-center">
                        <div className="absolute inset-x-12 top-12 h-1 overflow-hidden rounded-full bg-violet-100">
                            <span className="progress-sweep block h-full w-1/3 rounded-full bg-violet-600" />
                        </div>
                        <div className="relative w-full max-w-sm rounded-2xl border border-slate-200 bg-white p-6 shadow-xl shadow-slate-200/60">
                            <div className="flex items-center justify-between">
                                <span className="text-xs font-bold text-slate-400">SCENE INTELLIGENCE</span>
                                <BrainCircuit size={20} className="text-violet-600" />
                            </div>
                            <div className="mt-7 space-y-3">
                                {[88, 72, 94, 60].map((width, index) => (
                                    <div key={width} className={`h-2.5 rounded-full ${index === 2 ? 'bg-violet-500' : 'bg-slate-200'}`} style={{ width: `${width}%` }} />
                                ))}
                            </div>
                            <div className="mt-8 flex flex-wrap gap-2">
                                {['Scenes', 'Characters', 'Tone', 'Opportunities'].map((tag, index) => (
                                    <span key={tag} className={`rounded-full px-3 py-1.5 text-[11px] font-semibold ${['bg-blue-100 text-blue-700', 'bg-violet-100 text-violet-700', 'bg-emerald-100 text-emerald-700', 'bg-amber-100 text-amber-700'][index]}`}>{tag}</span>
                                ))}
                            </div>
                        </div>
                        <p className="absolute bottom-10 text-center text-xs text-slate-500">The browser sends your script to FastAPI.<br />Gemini credentials remain on the backend.</p>
                    </div>
                </div>
            </section>
        </AppShell>
    );
}

// Explain a lost in-memory upload after a hard refresh.
function InterruptedState() {
    return (
        <div className="mt-5 rounded-xl border border-amber-200 bg-amber-50 p-5">
            <p className="text-sm font-semibold text-amber-900">The upload session was interrupted.</p>
            <p className="mt-1 text-sm text-amber-800">Files cannot be retained after a full browser refresh.</p>
            <Link href="/" className="mt-4 inline-flex rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white">Choose the file again</Link>
        </div>
    );
}

// Surface API and Gemini errors with clear retry and recovery actions.
function ErrorState({ message, onRetry }: { message: string | null; onRetry: () => void }) {
    return (
        <div className="mt-5 rounded-xl border border-rose-200 bg-rose-50 p-5" role="alert">
            <div className="flex gap-3">
                <Circle className="mt-1 shrink-0 text-rose-600" size={12} fill="currentColor" />
                <div>
                    <p className="text-sm font-semibold text-rose-900">The analysis did not complete.</p>
                    <p className="mt-1 text-sm leading-6 text-rose-800">{message || 'The backend returned an unexpected error.'}</p>
                </div>
            </div>
            <div className="mt-4 flex flex-wrap gap-3">
                <button type="button" onClick={onRetry} className="inline-flex items-center gap-2 rounded-lg bg-rose-700 px-4 py-2 text-sm font-semibold text-white hover:bg-rose-800"><RotateCcw size={15} /> Retry analysis</button>
                <Link href="/" className="rounded-lg border border-rose-200 bg-white px-4 py-2 text-sm font-semibold text-rose-800">Choose another file</Link>
            </div>
        </div>
    );
}
