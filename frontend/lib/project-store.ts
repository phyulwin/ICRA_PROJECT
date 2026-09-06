// frontend/lib/project-store.ts
import type { ProjectSnapshot } from './types';

// Namespace local Phase 2 state so future persistent storage can replace it cleanly.
const STORAGE_PREFIX = 'meme-director:project:';

// Persist one completed analysis on the current device for route navigation and refreshes.
export function saveProject(snapshot: ProjectSnapshot): void {
    try {
        window.localStorage.setItem(
            `${STORAGE_PREFIX}${snapshot.projectId}`,
            JSON.stringify(snapshot),
        );
    } catch {
        // Continue with in-memory state when browser storage is unavailable.
    }
}

// Read completed project state without throwing on malformed or unavailable browser storage.
export function loadProject(projectId: string): ProjectSnapshot | null {
    try {
        const value = window.localStorage.getItem(`${STORAGE_PREFIX}${projectId}`);
        return value ? (JSON.parse(value) as ProjectSnapshot) : null;
    } catch {
        return null;
    }
}

