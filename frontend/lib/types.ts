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
export type ReferenceType = 'all' | 'tiktok_short_form' | 'instagram_reels' | 'memes' | 'reaction_gifs' | 'anime' | 'film' | 'tv' | 'internet_culture';
export type ReferenceEra = 'any' | 'trending_current' | '2020_present' | '2015_2019' | '2010_2014' | '2000s' | 'pre_2000';
export type MatchFor = 'best_overall' | 'performance' | 'facial_expression' | 'situation' | 'visual_composition' | 'body_language' | 'comedic_timing' | 'emotional_beat' | 'camera_framing';
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
    recognition: number;
    user_intent: string;
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
    discovered_from_queries: string[];
    search_family: string;
    published_at: string | null;
    source_metadata: Record<string, unknown>;
}

export interface ReferenceAssessment {
    candidate_id: string;
    emotional_similarity: number;
    situational_similarity: number;
    facial_expression_similarity: number;
    performance_similarity: number;
    body_language_similarity: number;
    visual_similarity: number;
    acting_similarity: number;
    timing_similarity: number;
    camera_framing_similarity: number;
    recognizability: number;
    cultural_relevance: number;
    artifact_verified: boolean;
    cultural_reference_type: CulturalReferenceType;
    artifact_quality: number;
    artifact_evidence: string;
    match_reason: string;
    tags: string[];
    useful_directing_elements: string[];
    best_for: string[];
    recognizability_is_inferred: boolean;
}

// Mirror Gemini's structured preference-aware retrieval strategy.
export interface SearchPlan {
    creative_target: string;
    comedic_or_dramatic_mechanism: string;
    desired_visual_action: string;
    desired_performance: string;
    desired_emotional_beat: string;
    desired_reference_types: string[];
    platform_targets: string[];
    era_intent: string;
    ranking_priority: string;
    queries: string[];
    negative_intents: string[];
    reformulation_diagnosis: string | null;
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
    search_plan: SearchPlan | null;
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
    search_plan: SearchPlan | null;
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

// Represent the validated Gemini directing plan returned through FastAPI.
export interface DirectingGuidance {
    reference_id: string;
    reference_title: string;
    scene_id: string;
    creative_intent: string;
    performance: string[];
    facial_expression: string[];
    body_language: string[];
    blocking: string[];
    camera: string[];
    framing: string[];
    shot_sequence: string[];
    timing: string[];
    editing: string[];
    sound: string[];
    visual_style: string[];
    what_to_borrow: string[];
    what_not_to_copy: string[];
    concise_director_note: string;
}

// Carry server-owned guidance identity so refresh and board saves remain durable.
export interface DirectingGuidanceResult {
    guidance_id: string;
    project_id: string;
    search_id: string;
    scene_id: string;
    reference_url: string;
    source_domain: string;
    guidance: DirectingGuidance;
}

// Mirror Firestore-backed Library reference records returned by FastAPI.
export interface SavedReference {
    id: string;
    project_id: string;
    scene_id: string;
    scene_heading: string;
    scene_excerpt: string;
    reference_id: string;
    reference_title: string;
    reference_url: string;
    source_domain: string;
    provider: string;
    description: string;
    overall_score: number;
    score_breakdown: Record<string, unknown>;
    match_reason: string;
    reference_type: string;
    image_url: string | null;
    tags: string[];
    created_at: string;
    updated_at: string;
}

// Mirror Firestore-backed directing boards returned by FastAPI.
export interface SavedDirectingBoard {
    id: string;
    project_id: string;
    scene_id: string;
    scene_heading: string;
    selected_reference: RankedReference;
    directing_guidance: DirectingGuidance;
    user_title: string;
    notes: string;
    created_at: string;
    updated_at: string;
}
