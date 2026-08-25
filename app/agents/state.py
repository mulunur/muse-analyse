"""Состояние графа персонализированных идей контента."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class RhythmFeatures(BaseModel):
    bpm: float
    beat_confidence: float
    beats_count: int
    onset_rate: float | None = None
    beat_loudness: float | None = None
    beat_loudness_band_ratio: float | None = None
    avg_beat_interval_sec: float | None = None


class TonalFeatures(BaseModel):
    key: str
    scale: str
    key_strength: float
    tuning_frequency_hz: float | None = None
    danceability: float | None = None
    danceability_dfa: float | None = None
    top_chords: list[dict[str, Any]] = Field(default_factory=list)


class DynamicsFeatures(BaseModel):
    loudness_ebu128_lufs: float | None = None
    loudness_db: float | None = None
    dynamic_complexity: float | None = None
    replay_gain_db: float | None = None
    rms: float | None = None


class SpectralFeatures(BaseModel):
    spectral_centroid_hz: float
    spectral_brightness: float
    spectral_rolloff_hz: float
    spectral_flux: float
    zero_crossing_rate: float
    mfcc_coefficients: list[float]


class AudioFeatures(BaseModel):
    file: str
    essentia_version: str
    duration_sec: float
    sample_rate: int
    rhythm: RhythmFeatures
    tonal: TonalFeatures
    dynamics: DynamicsFeatures
    spectral: SpectralFeatures
    energy: float


class VoiceProfile(BaseModel):
    tone: str
    recurring_themes: list[str]
    avoid_list: list[str]
    register: Literal["classical", "contemporary"] = "classical"


class TrendContext(BaseModel):
    active_playlists: list[str]
    genre_context_summary: str
    source_urls: list[str]


class ContentIdea(BaseModel):
    id: str
    format: Literal[
        "instagram_caption",
        "playlist_pitch_email",
        "press_quote_card",
        "story_series",
        "bio_snippet",
    ]
    hook: str
    rationale: str
    voice_alignment: str
    trend_relevance: str | None = None


class GrowthState(BaseModel):
    audio_features: AudioFeatures | None = None
    artist_materials: list[str] = Field(default_factory=list)
    voice_profile: VoiceProfile | None = None
    trend_context: TrendContext | None = None
    content_ideas: list[ContentIdea] = Field(default_factory=list)
    selected_idea_ids: list[str] = Field(default_factory=list)
    drafts: dict[str, str] = Field(default_factory=dict)
    critique_feedback: str | None = None
    critique_passed: bool = False
    retry_count: int = 0
    audio_path: str | None = None
