// frontend/lib/reference-store.ts
import type { ReferenceSearchResponse } from './types';

// Namespace Phase 3 results independently from screenplay analysis snapshots.
const STORAGE_PREFIX = 'meme-director:references:';


// Persist only returned reference metadata, never backend credentials or uploaded files.
export function saveReferenceResult(
    projectId: string,
    sceneId: string,
    result: ReferenceSearchResponse,
): void {
    try {
        window.localStorage.setItem(
            `${STORAGE_PREFIX}${projectId}:${sceneId}`,
            JSON.stringify(result),
        );
    } catch {
        // Continue with component state when browser storage is unavailable.
    }
}


// Restore the latest completed search for convenient scene navigation.
export function loadReferenceResult(
    projectId: string,
    sceneId: string,
): ReferenceSearchResponse | null {
    try {
        const value = window.localStorage.getItem(
            `${STORAGE_PREFIX}${projectId}:${sceneId}`,
        );
        return value ? (JSON.parse(value) as ReferenceSearchResponse) : null;
    } catch {
        return null;
    }
}
