// frontend/lib/use-project.ts
'use client';

import { useEffect, useState } from 'react';
import { useAnalysis } from '@/app/providers';
import { loadProject } from './project-store';
import type { ProjectSnapshot } from './types';

// Resolve a completed project from live context first, then browser-local storage.
export function useProject(projectId: string) {
    const { result: liveResult } = useAnalysis();
    const [snapshot, setSnapshot] = useState<ProjectSnapshot | null>(null);
    const [loading, setLoading] = useState(true);

    // Resolve browser storage after hydration to keep server and client markup aligned.
    useEffect(() => {
        const timer = window.setTimeout(() => {
            if (liveResult?.projectId === projectId) {
                setSnapshot(liveResult);
            } else {
                setSnapshot(loadProject(projectId));
            }
            setLoading(false);
        }, 0);
        return () => window.clearTimeout(timer);
    }, [liveResult, projectId]);

    return { snapshot, loading };
}
