// frontend/app/providers.tsx
'use client';

import {
    createContext,
    useCallback,
    useContext,
    useMemo,
    useState,
    type ReactNode,
} from 'react';
import { uploadScreenplay } from '@/lib/api';
import type { ProjectSnapshot } from '@/lib/types';

type JobStatus = 'idle' | 'processing' | 'success' | 'error';

interface AnalysisContextValue {
    status: JobStatus;
    projectId: string | null;
    fileName: string | null;
    error: string | null;
    result: ProjectSnapshot | null;
    beginAnalysis: (file: File) => string;
    retryAnalysis: () => string | null;
}

// Use one provider to retain the uploaded File while navigating to the processing route.
const AnalysisContext = createContext<AnalysisContextValue | null>(null);

// Coordinate the real backend request and save only completed results.
export function AnalysisProvider({ children }: { children: ReactNode }) {
    const [status, setStatus] = useState<JobStatus>('idle');
    const [projectId, setProjectId] = useState<string | null>(null);
    const [fileName, setFileName] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [result, setResult] = useState<ProjectSnapshot | null>(null);
    const [pendingFile, setPendingFile] = useState<File | null>(null);

    // Start a new project analysis immediately and return its route identifier.
    const beginAnalysis = useCallback((file: File): string => {
        const id = crypto.randomUUID();
        setProjectId(id);
        setFileName(file.name);
        setPendingFile(file);
        setStatus('processing');
        setError(null);
        setResult(null);

        void uploadScreenplay(file, id)
            .then((analysis) => {
                if (analysis.scenes.length === 0) {
                    throw new Error('No screenplay scenes were detected in this document.');
                }
                const snapshot: ProjectSnapshot = {
                    projectId: id,
                    analyzedAt: new Date().toISOString(),
                    result: analysis,
                };
                setResult(snapshot);
                setStatus('success');
            })
            .catch((reason: unknown) => {
                setError(
                    reason instanceof Error
                        ? reason.message
                        : 'The screenplay could not be analyzed.',
                );
                setStatus('error');
            });
        return id;
    }, []);

    // Retry only when the original browser File remains available in memory.
    const retryAnalysis = useCallback((): string | null => {
        if (!pendingFile) {
            setError('Return to upload and choose the screenplay again.');
            return null;
        }
        return beginAnalysis(pendingFile);
    }, [beginAnalysis, pendingFile]);

    // Memoize context identity to avoid unnecessary page rerenders.
    const value = useMemo(
        () => ({
            status,
            projectId,
            fileName,
            error,
            result,
            beginAnalysis,
            retryAnalysis,
        }),
        [status, projectId, fileName, error, result, beginAnalysis, retryAnalysis],
    );

    return <AnalysisContext.Provider value={value}>{children}</AnalysisContext.Provider>;
}

// Enforce provider placement for all project workflow components.
export function useAnalysis(): AnalysisContextValue {
    const context = useContext(AnalysisContext);
    if (!context) {
        throw new Error('useAnalysis must be used within AnalysisProvider.');
    }
    return context;
}
