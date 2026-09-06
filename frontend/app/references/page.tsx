// frontend/app/references/page.tsx
import Link from 'next/link';
import { ArrowRight, Search } from 'lucide-react';
import { AppShell } from '@/components/app-shell';

// Direct users into the active scene-scoped Parallel reference workflow.
export default function ReferencesPage() {
    return (
        <AppShell>
            <section className="mx-auto grid min-h-[calc(100vh-4rem)] max-w-3xl place-items-center px-5 py-12 text-center">
                <div className="rounded-3xl border border-slate-200 bg-white p-10 shadow-sm">
                    <span className="mx-auto grid size-14 place-items-center rounded-2xl bg-violet-100 text-violet-700"><Search size={26} /></span>
                    <h1 className="mt-5 text-3xl font-bold tracking-[-0.03em] text-slate-950">Parallel reference search is active</h1>
                    <p className="mx-auto mt-3 max-w-xl text-sm leading-6 text-slate-600">Open an analyzed screenplay scene to search the live web, evaluate real candidates with Gemini, and inspect source-linked ranking details.</p>
                    <Link href="/" className="mt-6 inline-flex items-center gap-2 rounded-lg bg-violet-700 px-5 py-3 text-sm font-semibold text-white hover:bg-violet-800">Upload or open a screenplay <ArrowRight size={15} /></Link>
                </div>
            </section>
        </AppShell>
    );
}
