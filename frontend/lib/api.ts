// frontend/lib/api.ts
import type {
    ReferenceSearchPreferences,
    ReferenceSearchResponse,
    ProjectDetail,
    ProjectRecord,
    RefinementRecord,
    SearchDetail,
    SearchRecord,
    SceneAnalysis,
    DirectingGuidanceResult,
    SavedDirectingBoard,
    SavedReference,
    ScreenplayAnalysisResult,
    ScreenplayScene,
} from './types';
import { authenticatedFetch } from './firebase-auth';

// Keep the backend origin centralized and configurable for local or hosted environments.
const configuredApiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
if (!configuredApiBaseUrl) {
    throw new Error('NEXT_PUBLIC_API_BASE_URL must be configured.');
}
const API_BASE_URL = configuredApiBaseUrl.endsWith('/')
    ? configuredApiBaseUrl.slice(0, -1)
    : configuredApiBaseUrl;

// Convert FastAPI error bodies and connectivity failures into useful interface messages.
async function parseResponse<T>(response: Response): Promise<T> {
    if (response.ok) {
        return response.json() as Promise<T>;
    }

    try {
        const body = (await response.json()) as { detail?: string };
        throw new Error(body.detail || `Analysis failed with status ${response.status}.`);
    } catch (error) {
        if (error instanceof Error && error.message !== 'Unexpected end of JSON input') {
            throw error;
        }
        throw new Error(`Analysis failed with status ${response.status}.`);
    }
}

// Send screenplay files only to FastAPI; the browser never communicates with Gemini directly.
export async function uploadScreenplay(file: File, projectId: string): Promise<ScreenplayAnalysisResult> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('project_id', projectId);

    try {
        const response = await authenticatedFetch(`${API_BASE_URL}/api/v1/screenplays/analyze`, {
            method: 'POST',
            body: formData,
        });
        return await parseResponse<ScreenplayAnalysisResult>(response);
    } catch (error) {
        if (error instanceof TypeError) {
            throw new Error(
                'Cannot reach the configured analysis service. Please try again shortly.',
            );
        }
        throw error;
    }
}

// Send existing Phase 2 state to FastAPI while Parallel credentials remain server-only.
export async function findCulturalReferences(
    projectId: string,
    scene: ScreenplayScene,
    sceneAnalysis: SceneAnalysis,
    preferences: ReferenceSearchPreferences,
    signal?: AbortSignal,
    requestId?: string,
): Promise<ReferenceSearchResponse> {
    try {
        const response = await authenticatedFetch(
            `${API_BASE_URL}/api/v1/scenes/${encodeURIComponent(scene.scene_id)}/references`,
            {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    ...(requestId ? { 'X-Search-Request-ID': requestId } : {}),
                },
                body: JSON.stringify({
                    project_id: projectId,
                    scene,
                    scene_analysis: sceneAnalysis,
                    preferences,
                }),
                signal,
            },
        );
        return await parseResponse<ReferenceSearchResponse>(response);
    } catch (error) {
        if (error instanceof TypeError) {
            throw new Error(
                'Cannot reach the configured reference service. Please try again shortly.',
            );
        }
        throw error;
    }
}

// Notify FastAPI across Cloud Run instances before aborting the local fetch.
export async function cancelCulturalReferenceSearch(requestId: string): Promise<void> {
    try {
        await authenticatedFetch(`${API_BASE_URL}/api/v1/reference-searches/${encodeURIComponent(requestId)}/cancel`, {
            method: 'POST',
            keepalive: true,
        });
    } catch {
        // AbortController and server disconnect monitoring remain fallback safeguards.
    }
}

export async function listProjects(): Promise<ProjectRecord[]> {
    return request<ProjectRecord[]>('/api/v1/projects');
}

export async function getProject(projectId: string): Promise<ProjectDetail> {
    return request<ProjectDetail>(`/api/v1/projects/${encodeURIComponent(projectId)}`);
}

export async function listSearches(projectId: string, sceneId: string): Promise<SearchRecord[]> {
    return request<SearchRecord[]>(`/api/v1/projects/${encodeURIComponent(projectId)}/scenes/${encodeURIComponent(sceneId)}/searches`);
}

export async function getSearch(projectId: string, sceneId: string, searchId: string): Promise<SearchDetail> {
    return request<SearchDetail>(`/api/v1/projects/${encodeURIComponent(projectId)}/scenes/${encodeURIComponent(sceneId)}/searches/${encodeURIComponent(searchId)}`);
}

export async function updateSelection(projectId: string, sceneId: string, searchId: string | null, referenceId: string | null): Promise<ProjectDetail> {
    return request<ProjectDetail>(`/api/v1/projects/${encodeURIComponent(projectId)}/scenes/${encodeURIComponent(sceneId)}/selection`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ search_id: searchId, reference_id: referenceId }),
    });
}

export async function listRefinements(projectId: string, sceneId: string): Promise<RefinementRecord[]> {
    return request<RefinementRecord[]>(`/api/v1/projects/${encodeURIComponent(projectId)}/scenes/${encodeURIComponent(sceneId)}/refinements`);
}

// Generate guidance from one server-persisted Parallel reference.
export async function generateDirectingGuidance(projectId: string, sceneId: string, searchId: string, referenceId: string): Promise<DirectingGuidanceResult> {
    return request<DirectingGuidanceResult>(`/api/v1/projects/${encodeURIComponent(projectId)}/scenes/${encodeURIComponent(sceneId)}/directing-guidance`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ search_id: searchId, reference_id: referenceId }),
    });
}

// Restore the latest persisted directing draft after navigation or refresh.
export async function getLatestDirectingGuidance(projectId: string, sceneId: string): Promise<DirectingGuidanceResult> {
    return request<DirectingGuidanceResult>(`/api/v1/projects/${encodeURIComponent(projectId)}/scenes/${encodeURIComponent(sceneId)}/directing-guidance`);
}

// Save a real ranked reference through FastAPI; Firestore is never exposed to the browser.
export async function saveLibraryReference(projectId: string, sceneId: string, searchId: string, referenceId: string): Promise<SavedReference> {
    return request<SavedReference>(`/api/v1/projects/${encodeURIComponent(projectId)}/library/references`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scene_id: sceneId, search_id: searchId, reference_id: referenceId }),
    });
}

// List durable references for one project.
export async function listLibraryReferences(projectId: string): Promise<SavedReference[]> {
    return request<SavedReference[]>(`/api/v1/projects/${encodeURIComponent(projectId)}/library/references`);
}

// Delete one exact durable reference.
export async function deleteLibraryReference(projectId: string, itemId: string): Promise<void> {
    await requestWithoutBody(`/api/v1/projects/${encodeURIComponent(projectId)}/library/references/${encodeURIComponent(itemId)}`, { method: 'DELETE' });
}

// Save a board from a server-generated guidance draft.
export async function saveDirectingBoard(projectId: string, sceneId: string, guidanceId: string, userTitle: string, notes: string): Promise<SavedDirectingBoard> {
    return request<SavedDirectingBoard>(`/api/v1/projects/${encodeURIComponent(projectId)}/library/boards`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scene_id: sceneId, guidance_id: guidanceId, user_title: userTitle, notes }),
    });
}

// List durable directing boards for one project.
export async function listDirectingBoards(projectId: string): Promise<SavedDirectingBoard[]> {
    return request<SavedDirectingBoard[]>(`/api/v1/projects/${encodeURIComponent(projectId)}/library/boards`);
}

// Delete one exact durable directing board.
export async function deleteDirectingBoard(projectId: string, boardId: string): Promise<void> {
    await requestWithoutBody(`/api/v1/projects/${encodeURIComponent(projectId)}/library/boards/${encodeURIComponent(boardId)}`, { method: 'DELETE' });
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await authenticatedFetch(`${API_BASE_URL}${path}`, init);
    return parseResponse<T>(response);
}

// Handle successful 204 responses without attempting to parse an empty JSON body.
async function requestWithoutBody(path: string, init?: RequestInit): Promise<void> {
    const response = await authenticatedFetch(`${API_BASE_URL}${path}`, init);
    if (!response.ok) {
        await parseResponse<never>(response);
    }
}
