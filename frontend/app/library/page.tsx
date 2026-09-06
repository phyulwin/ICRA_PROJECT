'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { ArrowRight, Archive, FileText, LoaderCircle } from 'lucide-react';
import { AppShell } from '@/components/app-shell';
import { listProjects } from '@/lib/api';
import type { ProjectRecord } from '@/lib/types';

// Show durable projects without loading their nested scenes or references.
export default function LibraryPage() {
    const [projects, setProjects] = useState<ProjectRecord[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        void listProjects()
            .then(setProjects)
            .catch((reason) => setError(reason instanceof Error ? reason.message : 'Projects could not be loaded.'))
            .finally(() => setLoading(false));
    }, []);

    return (
        <AppShell>
            <section className="mx-auto max-w-6xl px-5 py-8 sm:px-8 sm:py-10">
                <header className="flex items-end justify-between gap-4 border-b border-slate-200 pb-7">
                    <div>
                        <p className="text-xs font-bold uppercase tracking-[0.14em] text-violet-700">Workspace</p>
                        <h1 className="mt-1 text-3xl font-bold tracking-[-0.03em] text-slate-950">Your projects</h1>
                        <p className="mt-2 text-sm text-slate-500">Return to a screenplay, its scenes, and the references you discovered.</p>
                    </div>
                    <Link href="/" className="hidden items-center gap-2 rounded-lg bg-violet-700 px-4 py-2.5 text-sm font-semibold text-white hover:bg-violet-800 sm:inline-flex"><FileText size={16} /> New screenplay</Link>
                </header>
                {loading && <div className="flex items-center gap-2 py-16 text-sm text-slate-500"><LoaderCircle size={18} className="animate-spin" /> Loading projects</div>}
                {error && <p className="mt-8 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">{error}</p>}
                {!loading && !error && projects.length === 0 && <div className="mt-8 rounded-2xl border border-dashed border-slate-300 bg-white px-6 py-16 text-center"><Archive className="mx-auto text-violet-600" size={30} /><h2 className="mt-4 font-bold text-slate-950">No saved projects yet</h2><p className="mt-2 text-sm text-slate-500">Upload a screenplay to create your first durable workspace.</p><Link href="/" className="mt-5 inline-flex rounded-lg bg-violet-700 px-4 py-2.5 text-sm font-semibold text-white">Analyze a screenplay</Link></div>}
                <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                    {projects.map((project) => <Link key={project.project_id} href={`/projects/${project.project_id}/scenes`} className="group rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition hover:-translate-y-0.5 hover:border-violet-200 hover:shadow-md"><div className="flex items-start justify-between gap-3"><span className="grid size-10 place-items-center rounded-xl bg-violet-100 text-violet-700"><FileText size={19} /></span><ArrowRight size={17} className="text-slate-400 transition group-hover:translate-x-1 group-hover:text-violet-700" /></div><h2 className="mt-5 truncate font-bold text-slate-950">{project.title}</h2><p className="mt-1 truncate text-xs text-slate-500">{project.filename}</p><div className="mt-5 flex items-center justify-between text-xs text-slate-500"><span>{project.scene_count} {project.scene_count === 1 ? 'scene' : 'scenes'}</span><time dateTime={project.updated_at}>{new Date(project.updated_at).toLocaleDateString()}</time></div></Link>)}
                </div>
            </section>
        </AppShell>
    );
}

