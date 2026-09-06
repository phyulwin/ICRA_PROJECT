// frontend/components/project-state.tsx
import Link from 'next/link';
import { FileQuestion, LoaderCircle } from 'lucide-react';

// Provide a consistent loading state while browser-local project data is resolved.
export function ProjectLoading() {
    return (
        <div className="grid min-h-[calc(100vh-4rem)] place-items-center px-6">
            <div className="text-center text-slate-600">
                <LoaderCircle className="mx-auto animate-spin text-violet-700" size={28} />
                <p className="mt-3 text-sm font-medium">Opening script analysis…</p>
            </div>
        </div>
    );
}

// Explain missing local state and offer a direct recovery action.
export function ProjectNotFound() {
    return (
        <div className="grid min-h-[calc(100vh-4rem)] place-items-center px-6">
            <div className="max-w-md rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-sm">
                <FileQuestion className="mx-auto text-violet-600" size={32} />
                <h1 className="mt-4 text-xl font-bold text-slate-950">Analysis not available</h1>
                <p className="mt-2 text-sm leading-6 text-slate-600">This Phase 2 project is stored in this browser after analysis. Upload the screenplay again to rebuild it.</p>
                <Link href="/" className="mt-5 inline-flex rounded-lg bg-violet-700 px-4 py-2.5 text-sm font-semibold text-white hover:bg-violet-800">Return to upload</Link>
            </div>
        </div>
    );
}

