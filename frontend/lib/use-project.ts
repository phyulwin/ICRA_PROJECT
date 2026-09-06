// frontend/lib/use-project.ts
'use client';

import { useEffect, useState } from 'react';
import { useAnalysis } from '@/app/providers';
import { getProject } from './api';
import type { ProjectSnapshot } from './types';

// Resolve a completed project from FastAPI, with the live result as a local fallback.
export function useProject(projectId: string) {
    const { result: liveResult } = useAnalysis();
    const [snapshot, setSnapshot] = useState<ProjectSnapshot | null>(null);
    const [loading, setLoading] = useState(true);

    // Resolve browser storage after hydration to keep server and client markup aligned.
    useEffect(() => {
        let cancelled = false;
        void getProject(projectId)
            .then((project) => {
                if (cancelled) return;
                setSnapshot({
                    projectId: project.project_id,
                    analyzedAt: project.updated_at,
                    result: {
                        project_id: project.project_id,
                        filename: project.filename,
                        media_type: String(project.screenplay_metadata.media_type ?? ''),
                        character_count: Number(project.screenplay_metadata.character_count ?? 0),
                        scenes: project.scenes,
                    },
                });
            })
            .catch(() => {
                // Keep the just-completed in-memory result available during local development.
                if (!cancelled && liveResult?.projectId === projectId) setSnapshot(liveResult);
            })
            .finally(() => {
                if (!cancelled) setLoading(false);
            });
        return () => { cancelled = true; };
    }, [liveResult, projectId]);

    return { snapshot, loading };
}
