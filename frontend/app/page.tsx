// frontend/app/page.tsx
'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { BrainCircuit, Clapperboard, FileSearch, Sparkles } from 'lucide-react';
import { AppShell } from '@/components/app-shell';
import { UploadDropzone } from '@/components/upload-dropzone';
import { useAnalysis } from './providers';

const SAMPLE_SCRIPT = `INT. APARTMENT - NIGHT

John confidently tells everyone he didn't eat the cake.

Everyone looks behind him.

Chocolate frosting covers his shirt.

John slowly stops smiling.`;

// Present the upload-first product surface and enter the real analysis workflow.
export default function UploadPage() {
    const router = useRouter();
    const { beginAnalysis } = useAnalysis();
    const [file, setFile] = useState<File | null>(null);
    const [error, setError] = useState<string | null>(null);

    // Validate extension and file size before any network request is made.
    function selectFile(nextFile: File | null) {
        setError(null);
        if (!nextFile) {
            setFile(null);
            return;
        }
        const extension = `.${nextFile.name.split('.').pop()?.toLowerCase()}`;
        if (!['.pdf', '.txt', '.fountain'].includes(extension)) {
            setFile(null);
            setError('Choose a PDF, TXT, or Fountain screenplay.');
            return;
        }
        if (nextFile.size === 0) {
            setFile(null);
            setError('This screenplay is empty. Choose a file with script content.');
            return;
        }
        if (nextFile.size > 20 * 1024 * 1024) {
            setFile(null);
            setError('Screenplays must be 20 MB or smaller.');
            return;
        }
        setFile(nextFile);
    }

    // Create an in-memory File so the sample follows the same real backend route.
    function useSampleScript() {
        selectFile(new File([SAMPLE_SCRIPT], 'caught-in-the-act.fountain', { type: 'text/plain' }));
    }

    // Begin Gemini analysis once and navigate to its progress workspace.
    function analyzeScript() {
        if (!file) {
            setError('Choose a screenplay before starting analysis.');
            return;
        }
        const projectId = beginAnalysis(file);
        router.push(`/projects/${projectId}/processing`);
    }

    return (
        <AppShell>
            <section className="mx-auto flex min-h-[calc(100vh-4.25rem)] max-w-6xl flex-col items-center justify-center px-5 py-12 sm:px-8">
                <div className="w-full max-w-3xl text-center">
                    <span className="inline-flex items-center gap-2 rounded-full border border-[#9ed9ee] bg-white px-3.5 py-1.5 text-xs font-semibold text-[#168acd] shadow-sm">
                        <Sparkles size={14} aria-hidden="true" />
                        Gemini-powered script intelligence
                    </span>
                    <h1 className="mx-auto mt-6 max-w-2xl text-4xl font-bold tracking-[-0.045em] text-slate-950 sm:text-5xl">
                        Your screenplay,<br />ready for its next scene
                    </h1>
                    <p className="mx-auto mt-5 max-w-xl text-sm leading-6 text-slate-600 sm:text-base">
                        Upload a screenplay and uncover the moments where cultural references can sharpen performances, visual language, and storytelling.
                    </p>
                </div>

                <div className="mt-10 grid w-full max-w-2xl grid-cols-3 gap-3 sm:gap-8">
                    <Feature icon={FileSearch} label="Upload Script" />
                    <Feature icon={BrainCircuit} label="AI Analysis" />
                    <Feature icon={Clapperboard} label="Better Direction" />
                </div>

                <div className="mt-8 w-full max-w-3xl rounded-2xl border border-[#c9e1ec] bg-white/95 p-5 shadow-[0_12px_35px_rgba(35,111,145,0.12)] backdrop-blur sm:p-8">
                    <UploadDropzone file={file} error={error} onFile={selectFile} />
                    <div className="mt-5 flex flex-col-reverse items-center justify-between gap-3 sm:flex-row">
                        <button type="button" onClick={useSampleScript} className="text-sm font-semibold text-violet-700 hover:text-violet-900">
                            Try the sample scene
                        </button>
                        <button
                            type="button"
                            onClick={analyzeScript}
                            disabled={!file}
                            className="w-full rounded-lg bg-[#229ed9] px-6 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-[#168acd] disabled:cursor-not-allowed disabled:bg-slate-300 sm:w-auto"
                        >
                            Analyze Script
                        </button>
                    </div>
                </div>
            </section>
        </AppShell>
    );
}

// Summarize one stage of the product value proposition.
function Feature({ icon: Icon, label }: { icon: typeof FileSearch; label: string }) {
    return (
        <div className="flex flex-col items-center gap-2 text-center text-xs font-medium text-slate-600 sm:text-sm">
            <span className="grid size-10 place-items-center rounded-xl bg-white text-violet-700 shadow-sm ring-1 ring-slate-200">
                <Icon size={19} strokeWidth={1.8} aria-hidden="true" />
            </span>
            {label}
        </div>
    );
}
