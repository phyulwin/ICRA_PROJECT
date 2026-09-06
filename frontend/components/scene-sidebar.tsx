// frontend/components/scene-sidebar.tsx
'use client';

import Link from 'next/link';
import type { AnalyzedScene } from '@/lib/types';

interface SceneSidebarProps {
    projectId: string;
    scenes: AnalyzedScene[];
    activeSceneId: string;
}

// Keep scene navigation visible on detailed analysis routes.
export function SceneSidebar({ projectId, scenes, activeSceneId }: SceneSidebarProps) {
    return (
        <aside className="border-b border-slate-200 bg-slate-50/80 p-4 lg:min-h-[calc(100vh-4rem)] lg:w-64 lg:border-b-0 lg:border-r">
            <p className="px-2 pb-3 text-xs font-bold uppercase tracking-[0.14em] text-slate-500">Scenes</p>
            <nav aria-label="Screenplay scenes" className="flex gap-2 overflow-x-auto lg:flex-col lg:overflow-visible">
                {scenes.map((item, index) => {
                    const active = item.scene.scene_id === activeSceneId;
                    return (
                        <Link
                            key={item.scene.scene_id}
                            href={`/projects/${projectId}/scenes/${item.scene.scene_id}`}
                            className={`flex min-w-52 items-center gap-3 rounded-xl px-3 py-3 text-xs transition lg:min-w-0 ${active ? 'bg-violet-100 text-violet-900' : 'text-slate-600 hover:bg-white hover:text-slate-950'}`}
                        >
                            <span className={`font-bold ${active ? 'text-violet-700' : 'text-slate-400'}`}>{String(index + 1).padStart(2, '0')}</span>
                            <span className="truncate font-semibold">{shortHeading(item.scene.heading)}</span>
                        </Link>
                    );
                })}
            </nav>
        </aside>
    );
}

// Keep sidebar labels compact while retaining the full heading on the page.
function shortHeading(heading: string): string {
    const separator = heading.indexOf(' - ');
    return separator > 0 ? heading.slice(0, separator) : heading;
}

