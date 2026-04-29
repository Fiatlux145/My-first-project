"""
Application principale FastAPI pour NeuroFocus MVP.
Configure les routes API, CORS, et le cycle de vie de l'application.

Routes:
- GET /health: Vérification de santé
- POST /test/submit: Soumission des résultats de tests
- GET /recommendations: Génération de recommandations (pour tests directs)
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional

from .config import settings
from .db import init_db, get_db
from .models import (
    TestSubmission,
    TestResultsResponse,
    RecommendationPlan,
    HealthCheck,
    ObjectiveEnum
)
from .scoring import calculate_all_scores
from .recommendations import generate_recommendation_plan


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gestion du cycle de vie de l'application.
    Initialise la base de données au démarrage.
    """
    # Startup: Initialiser la DB
    await init_db()
    print(f"✅ {settings.app_name} démarré - DB initialisée")
    
    yield
    
    # Shutdown: Nettoyage si nécessaire
    print(f"👋 {settings.app_name} arrêté")


# Création de l'application FastAPI
app = FastAPI(
    title=settings.app_name,
    description="MVP d'évaluation cognitive avec scoring automatisé et recommandations personnalisées",
    version="1.0.0",
    lifespan=lifespan,
)

# Configuration CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthCheck, tags=["Health"])
async def health_check():
    """
    Vérification de santé de l'API.
    Retourne le statut de l'application.
    """
    return HealthCheck(
        status="healthy",
        app_name=settings.app_name
    )


@app.post("/test/submit", response_model=TestResultsResponse, tags=["Tests"])
async def submit_test_results(submission: TestSubmission):
    """
    Soumet les résultats des tests cognitifs et retourne:
    - Scores de concentration et mémoire
    - Profil cognitif identifié
    - Plan de recommandation personnalisé
    
    Corps de requête attendu:
    - objective: Objectif utilisateur (academic/professional/wellness/training)
    - n_back: Résultats optionnels du test N-Back
    - recall: Résultats optionnels du test Rappel
    
    Au moins un test doit être soumis.
    """
    try:
        # Calcul des scores
        scores = calculate_all_scores(
            n_back=submission.n_back,
            recall=submission.recall,
            simulated_cpt_error_rate=0.15  # Valeur par défaut simulée
        )
        
        # Génération du plan de recommandation
        recommendation = generate_recommendation_plan(
            concentration_score=scores["concentration_score"],
            memory_score=scores["memory_score"],
            profile=scores["profile"],
            objective=submission.objective
        )
        
        # Construction de la réponse
        response = TestResultsResponse(
            concentration_score=scores["concentration_score"],
            memory_score=scores["memory_score"],
            profile=scores["profile"],
            recommendation=recommendation
        )
        
        return response
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors du traitement des résultats: {str(e)}"
        )


@app.get("/recommendations", response_model=RecommendationPlan, tags=["Recommendations"])
async def get_recommendations(
    concentration_score: float,
    memory_score: float,
    objective: ObjectiveEnum
):
    """
    Génère un plan de recommandation basé sur des scores fournis directement.
    Utile pour tester le moteur de recommandation sans soumettre de tests.
    
    Query params:
    - concentration_score: Score de concentration (0-100)
    - memory_score: Score de mémoire (0-100)
    - objective: Objectif utilisateur
    """
    try:
        # Validation des scores
        if not (0 <= concentration_score <= 100):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Le score de concentration doit être entre 0 et 100"
            )
        
        if not (0 <= memory_score <= 100):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Le score de mémoire doit être entre 0 et 100"
            )
        
        # Détermination du profil
        from .scoring import determine_profile
        profile = determine_profile(concentration_score, memory_score)
        
        # Génération du plan
        recommendation = generate_recommendation_plan(
            concentration_score=concentration_score,
            memory_score=memory_score,
            profile=profile,
            objective=objective
        )
        
        return recommendation
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la génération des recommandations: {str(e)}"
        )


# Point d'entrée racine avec documentation
@app.get("/", tags=["Root"])
async def root():
    """
    Point d'entrée principal.
    Redirige vers la documentation API interactive.
    """
    return {
        "message": "Bienvenue sur NeuroFocus API",
        "docs": "/docs",
        "health": "/health",
        "disclaimer": "Outil d'auto-évaluation, non diagnostique. Ne remplace pas un avis médical professionnel."
    }
