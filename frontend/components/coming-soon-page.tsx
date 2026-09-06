// frontend/components/coming-soon-page.tsx
import Link from 'next/link';
import { Archive, ArrowLeft, Clock3, Search } from 'lucide-react';
import { AppShell } from './app-shell';

interface ComingSoonPageProps {
    section: 'References' | 'Library';
}

// Render intentional global navigation placeholders for work scheduled after Phase 2.
export function ComingSoonPage({ section }: ComingSoonPageProps) {
    const references = section === 'References';
    return (
        <AppShell>
            <section className="mx-auto grid min-h-[calc(100vh-4rem)] max-w-5xl place-items-center px-5 py-12 sm:px-8">
                <div className="w-full max-w-xl rounded-3xl border border-slate-200 bg-white p-10 text-center shadow-[0_18px_60px_rgba(30,35,60,0.08)]">
                    <span className="mx-auto grid size-14 place-items-center rounded-2xl bg-violet-100 text-violet-700">{references ? <Search size={27} /> : <Archive size={27} />}</span>
                    <span className="mt-5 inline-flex items-center gap-1.5 rounded-full bg-slate-100 px-3 py-1 text-[11px] font-bold uppercase tracking-[0.1em] text-slate-500"><Clock3 size={12} /> Coming in Phase 3</span>
                    <h1 className="mt-3 text-3xl font-bold tracking-[-0.035em] text-slate-950">{section}</h1>
                    <p className="mt-3 text-sm leading-6 text-slate-600">{references ? 'Ranked cultural references will live here after Parallel search is connected.' : 'Saved references and directing boards will live here in a future phase.'}</p>
                    <Link href="/" className="mt-6 inline-flex items-center gap-2 rounded-lg bg-violet-700 px-4 py-2.5 text-sm font-semibold text-white hover:bg-violet-800"><ArrowLeft size={15} /> Return to scripts</Link>
                </div>
            </section>
        </AppShell>
    );
}

