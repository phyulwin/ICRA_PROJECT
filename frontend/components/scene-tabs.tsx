// frontend/components/scene-tabs.tsx
import Link from 'next/link';

interface SceneTabsProps {
    projectId: string;
    sceneId: string;
    active: 'analysis' | 'references' | 'directing';
    queryCount: number;
}

// Preserve the final-product information architecture while Phase 3 remains disabled.
export function SceneTabs({ projectId, sceneId, active, queryCount }: SceneTabsProps) {
    const base = `/projects/${projectId}/scenes/${sceneId}`;
    const tabs = [
        { id: 'analysis', label: 'Analysis', href: base },
        { id: 'references', label: `References · ${queryCount}`, href: `${base}/references` },
        { id: 'directing', label: 'Directing Notes', href: `${base}/directing-notes` },
    ] as const;

    return (
        <nav aria-label="Scene detail sections" className="flex gap-6 border-b border-slate-200">
            {tabs.map((tab) => (
                <Link key={tab.id} href={tab.href} className={`relative py-3 text-xs font-semibold sm:text-sm ${active === tab.id ? 'text-violet-700' : 'text-slate-500 hover:text-slate-900'}`}>
                    {tab.label}
                    {active === tab.id && <span className="absolute inset-x-0 bottom-0 h-0.5 rounded-full bg-violet-600" />}
                </Link>
            ))}
        </nav>
    );
}

