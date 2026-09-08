// frontend/components/app-shell.tsx
'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Clapperboard } from 'lucide-react';
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
            <header className="h-[4.25rem] border-b border-[#168acd]/20 bg-[var(--navy-950)] text-white shadow-[0_2px_10px_rgba(24,126,181,0.15)]">
                <div className="mx-auto grid h-full max-w-[1500px] grid-cols-[1fr_auto_1fr] items-center px-5 sm:px-8">
                    <Link href="/" className="flex items-center gap-2.5 font-semibold tracking-[-0.02em]">
                        <span className="grid size-9 place-items-center rounded-full bg-white text-[var(--navy-950)] shadow-sm">
                            <Clapperboard size={18} strokeWidth={2.2} aria-hidden="true" />
                        </span>
                        <span className="text-[15px] tracking-[-0.01em]">MemeDirector</span>
                    </Link>

                    <nav aria-label="Primary navigation" className="col-start-2 flex h-full items-center gap-1 sm:gap-7">
                        <NavLink href="/" active={scriptActive}>Script</NavLink>
                        <NavLink href="/library" active={pathname === '/library'}>Library</NavLink>
                    </nav>

                </div>
            </header>
            <main className="workspace-bg min-h-[calc(100vh-4.25rem)]">{children}</main>
        </div>
    );
}

// Render one understated navigation item with an active underline.
function NavLink({ href, active, children }: { href: string; active: boolean; children: ReactNode }) {
    return (
        <Link
            href={href}
            className={`relative flex h-full items-center px-3 text-xs font-medium transition-colors sm:text-sm ${active ? 'text-white' : 'text-white/70 hover:text-white'}`}
        >
            {children}
            {active && <span className="absolute inset-x-2 bottom-2 h-0.5 rounded-full bg-white" />}
        </Link>
    );
}

