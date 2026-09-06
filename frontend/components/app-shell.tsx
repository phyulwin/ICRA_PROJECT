// frontend/components/app-shell.tsx
'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Clapperboard, UserRound } from 'lucide-react';
import type { ReactNode } from 'react';

interface AppShellProps {
    children: ReactNode;
}

// Keep navigation consistent across upload, processing, and analysis routes.
export function AppShell({ children }: AppShellProps) {
    const pathname = usePathname();
    const scriptActive = pathname === '/' || pathname.startsWith('/projects');

    return (
        <div className="min-h-screen bg-[var(--canvas)]">
            <header className="h-16 border-b border-white/10 bg-[var(--navy-950)] text-white shadow-sm">
                <div className="mx-auto flex h-full max-w-[1500px] items-center justify-between px-5 sm:px-8">
                    <Link href="/" className="flex items-center gap-2.5 font-semibold tracking-[-0.02em]">
                        <span className="grid size-8 place-items-center rounded-lg bg-white/10 text-violet-300">
                            <Clapperboard size={18} strokeWidth={2.2} aria-hidden="true" />
                        </span>
                        <span>MemeDirector</span>
                    </Link>

                    <nav aria-label="Primary navigation" className="flex h-full items-center gap-1 sm:gap-7">
                        <NavLink href="/" active={scriptActive}>Script</NavLink>
                        <NavLink href="/references" active={pathname === '/references'}>References</NavLink>
                        <NavLink href="/library" active={pathname === '/library'}>Library</NavLink>
                    </nav>

                    <div className="grid size-8 place-items-center rounded-full border border-white/15 bg-white/10 text-slate-200" aria-label="Guest profile">
                        <UserRound size={16} aria-hidden="true" />
                    </div>
                </div>
            </header>
            <main className="workspace-bg min-h-[calc(100vh-4rem)]">{children}</main>
        </div>
    );
}

// Render one understated navigation item with an active underline.
function NavLink({ href, active, children }: { href: string; active: boolean; children: ReactNode }) {
    return (
        <Link
            href={href}
            className={`relative flex h-full items-center px-2 text-xs font-medium transition-colors sm:text-sm ${active ? 'text-white' : 'text-slate-400 hover:text-white'}`}
        >
            {children}
            {active && <span className="absolute inset-x-2 bottom-0 h-0.5 bg-violet-500" />}
        </Link>
    );
}

