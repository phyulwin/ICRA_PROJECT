// frontend/lib/api.ts
import type {
    ReferenceSearchPreferences,
    ReferenceSearchResponse,
    SceneAnalysis,
    ScreenplayAnalysisResult,
    ScreenplayScene,
} from './types';

// Keep the backend origin centralized and configurable for local or hosted environments.
const configuredApiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000';
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
export async function uploadScreenplay(file: File): Promise<ScreenplayAnalysisResult> {
    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await fetch(`${API_BASE_URL}/api/v1/screenplays/analyze`, {
            method: 'POST',
            body: formData,
        });
        return await parseResponse<ScreenplayAnalysisResult>(response);
    } catch (error) {
        if (error instanceof TypeError) {
            throw new Error(
                'Cannot reach the analysis service. Confirm the FastAPI backend is running on port 8000.',
            );
        }
        throw error;
    }
}

// Send existing Phase 2 state to FastAPI while Parallel credentials remain server-only.
export async function findCulturalReferences(
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
                'Cannot reach the reference service. Confirm the FastAPI backend is running.',
            );
        }
        throw error;
    }
}
