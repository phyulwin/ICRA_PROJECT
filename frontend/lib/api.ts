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
    ScreenplayAnalysisResult,
    ScreenplayScene,
} from './types';

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
        const response = await fetch(`${API_BASE_URL}/api/v1/screenplays/analyze`, {
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
): Promise<ReferenceSearchResponse> {
    try {
        const response = await fetch(
            `${API_BASE_URL}/api/v1/scenes/${encodeURIComponent(scene.scene_id)}/references`,
            {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
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

async function request<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await fetch(`${API_BASE_URL}${path}`, init);
    return parseResponse<T>(response);
}
