// frontend/lib/types.ts
// Mirror the backend Pydantic contracts without exposing backend credentials.
export type ReferenceOpportunity =
    | 'no reference needed'
    | 'possible reference opportunity'
    | 'strong reference opportunity';

export interface ScreenplayScene {
    scene_id: string;
    heading: string;
    location: string;
    time_of_day: string | null;
    characters: string[];
    raw_text: string;
}

export interface CharacterIntention {
    character: string;
    intention: string;
}

export interface SceneAnalysis {
    scene_type: string;
    tone: string[];
    characters: string[];
    character_intentions: CharacterIntention[];
    primary_beat: string;
    emotions: string[];
    comedic_or_dramatic_mechanism: string;
    important_actions: string[];
    visual_characteristics: string[];
    cultural_concepts: string[];
    reference_opportunity: ReferenceOpportunity;
    reference_opportunity_score: number;
    reference_opportunity_reason: string;
    reference_queries: string[];
}

export interface AnalyzedScene {
    scene: ScreenplayScene;
    analysis: SceneAnalysis;
}

export interface ScreenplayAnalysisResult {
    project_id?: string | null;
    filename: string;
    media_type: string;
    character_count: number;
    scenes: AnalyzedScene[];
}

export interface ProjectSnapshot {
    projectId: string;
    analyzedAt: string;
    result: ScreenplayAnalysisResult;
}

export interface ProjectRecord {
    project_id: string;
    title: string;
    filename: string;
    created_at: string;
    updated_at: string;
    status: string;
    screenplay_metadata: Record<string, unknown>;
    selected_scene_id: string | null;
    latest_search_preferences: ReferenceSearchPreferences | null;
    scene_count: number;
    selected_reference_count: number;
}

export interface ProjectDetail extends ProjectRecord {
    scenes: AnalyzedScene[];
}

// Mirror backend search controls without exposing the server-side Parallel key.
export type ReferenceType = 'all' | 'memes' | 'internet' | 'film' | 'anime' | 'tiktok';
export type ReferenceEra = 'any' | '2000s' | '2010s' | '2020s' | 'current';
export type MatchFor = 'all' | 'acting' | 'situation' | 'visual' | 'timing';
export type CulturalReferenceType =
    | 'reaction_meme'
    | 'viral_video'
    | 'tiktok'
    | 'instagram_reel'
    | 'gif'
    | 'film_tv_moment'
    | 'anime_moment'
    | 'informational_article'
    | 'other';
export type SourcePlatform =
    | 'tiktok'
    | 'instagram'
    | 'youtube'
    | 'giphy'
    | 'tenor'
    | 'meme'
    | 'reddit'
    | 'film_tv'
    | 'web';

export interface ReferenceSearchPreferences {
    reference_type: ReferenceType;
    era: ReferenceEra;
    match_for: MatchFor;
    obscurity: number;
    max_results: number;
}

// Keep Parallel-owned source facts separate from Gemini-owned assessment fields.
export interface CulturalReferenceCandidate {
    id: string;
    title: string;
    url: string;
    source_domain: string;
    snippet: string;
    image_url: string | null;
    reference_type: ReferenceType | 'unclassified';
    cultural_reference_type: CulturalReferenceType;
    source_platform: SourcePlatform;
    discovered_from_query: string;
    published_at: string | null;
    source_metadata: Record<string, unknown>;
}

export interface ReferenceAssessment {
    candidate_id: string;
    emotional_similarity: number;
    situational_similarity: number;
    visual_similarity: number;
    acting_similarity: number;
    timing_similarity: number;
    recognizability: number;
    cultural_relevance: number;
    artifact_verified: boolean;
    cultural_reference_type: CulturalReferenceType;
    artifact_quality: number;
    artifact_evidence: string;
    match_reason: string;
    tags: string[];
}

export interface RankedReference {
    reference: CulturalReferenceCandidate;
    assessment: ReferenceAssessment;
    overall_score: number;
}

export interface SearchQueryFailure {
    query: string;
    error_type: string;
    message: string;
}

export interface ReferenceSearchResponse {
    scene_id: string;
    references: RankedReference[];
    raw_candidate_count: number;
    rejected_candidate_count: number;
    extracted_candidate_count: number;
    searched_queries: string[];
    failed_queries: SearchQueryFailure[];
    warnings: string[];
    partial_success: boolean;
    retry_count: number;
    search_id: string | null;
}

export interface SearchRecord {
    search_id: string;
    project_id: string;
    scene_id: string;
    queries: string[];
    preferences: ReferenceSearchPreferences;
    created_at: string;
    raw_candidate_count: number;
    retained_candidate_count: number;
    retry_count: number;
    status: string;
    failed_queries: SearchQueryFailure[];
    warnings: string[];
}

export interface SearchDetail extends SearchRecord {
    references: RankedReference[];
    chosen_reference_id: string | null;
}

export interface RefinementRecord {
    refinement_id: string;
    project_id: string;
    scene_id: string;
    user_text: string;
    parsed_preferences: ReferenceSearchPreferences;
    previous_search_id: string | null;
    resulting_search_id: string | null;
    created_at: string;
}
