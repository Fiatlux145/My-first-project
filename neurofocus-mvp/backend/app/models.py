"""
Modèles de données Pydantic pour la validation des requêtes/réponses API.
Respecte le typage strict et les contraintes du MVP.
"""
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Literal
from datetime import datetime
from enum import Enum


class ObjectiveEnum(str, Enum):
    """Objectifs utilisateur possibles."""
    ACADEMIC = "academic"
    PROFESSIONAL = "professional"
    WELLNESS = "wellness"
    TRAINING = "training"


class TestTypeEnum(str, Enum):
    """Types de tests cognitifs."""
    N_BACK = "n_back"
    RECALL = "recall"


# ==================== SCHÉMAS DE REQUÊTE ====================

class NBackResult(BaseModel):
    """Résultat d'un test N-Back."""
    level: int = Field(ge=1, le=10, description="Niveau atteint (1-10)")
    accuracy: float = Field(ge=0.0, le=1.0, description="Précision (0-1)")
    avg_reaction_time_ms: float = Field(ge=0, description="Temps de réaction moyen en ms")
    total_trials: int = Field(ge=1, description="Nombre total d'essais")
    correct_responses: int = Field(ge=0, description="Nombre de réponses correctes")


class RecallResult(BaseModel):
    """Résultat d'un test de rappel de liste."""
    words_presented: int = Field(default=10, description="Nombre de mots présentés")
    words_recalled: int = Field(ge=0, le=15, description="Nombre de mots rappelés correctement")
    presentation_time_sec: int = Field(default=15, description="Temps de présentation en secondes")
    recall_order_correct: int = Field(ge=0, description="Nombre de mots dans le bon ordre")


class TestSubmission(BaseModel):
    """Soumission complète des résultats de tests."""
    objective: ObjectiveEnum = Field(..., description="Objectif choisi par l'utilisateur")
    n_back: Optional[NBackResult] = Field(None, description="Résultats du test N-Back")
    recall: Optional[RecallResult] = Field(None, description="Résultats du test Rappel")
    session_id: Optional[str] = Field(None, description="ID de session anonymisé (optionnel)")
    
    @field_validator('n_back', 'recall')
    @classmethod
    def at_least_one_test(cls, v, info):
        """Valide qu'au moins un test est soumis."""
        return v
    
    def model_post_init(self, __context):
        """Validation personnalisée post-initialisation."""
        if self.n_back is None and self.recall is None:
            raise ValueError("Au moins un test (n_back ou recall) doit être soumis")


# ==================== SCHÉMAS DE RÉPONSE ====================

class CognitiveProfile(str, Enum):
    """Catégories de profil cognitif."""
    BALANCED = "equilibre"
    FOCUS_STRONG = "focus_fort"
    MEMORY_FRAGILE = "memoire_fragile"
    HIGH_VARIABILITY = "variabilite_haute"


class RecommendationItem(BaseModel):
    """Un élément de recommandation dans le plan."""
    activity: str = Field(..., description="Nom de l'activité")
    frequency: str = Field(..., description="Fréquence recommandée")
    duration: str = Field(..., description="Durée par session")
    tools: List[str] = Field(default_factory=list, description="Outils nécessaires")
    description: str = Field(..., description="Description détaillée")


class RecommendationPlan(BaseModel):
    """Plan de recommandation personnalisé."""
    profile: CognitiveProfile = Field(..., description="Profil cognitif identifié")
    concentration_score: float = Field(ge=0, le=100, description="Score de concentration")
    memory_score: float = Field(ge=0, le=100, description="Score de mémoire")
    activities: List[RecommendationItem] = Field(..., description="Liste des activités recommandées")
    retest_days: int = Field(default=30, description="Jours avant le prochain test recommandé")
    progress_tracking: str = Field(..., description="Instructions de suivi de progression")


class TestResultsResponse(BaseModel):
    """Réponse après soumission des tests."""
    concentration_score: float = Field(ge=0, le=100)
    memory_score: float = Field(ge=0, le=100)
    profile: CognitiveProfile
    recommendation: RecommendationPlan
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_schema_extra = {
            "example": {
                "concentration_score": 65.5,
                "memory_score": 72.0,
                "profile": "equilibre",
                "recommendation": {
                    "profile": "equilibre",
                    "concentration_score": 65.5,
                    "memory_score": 72.0,
                    "activities": [],
                    "retest_days": 30,
                    "progress_tracking": "..."
                },
                "created_at": "2024-01-15T10:30:00Z"
            }
        }


class HealthCheck(BaseModel):
    """Réponse de santé de l'API."""
    status: str = "healthy"
    app_name: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
