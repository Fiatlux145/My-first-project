"""
Moteur de recommandation personnalisé.
Génère un plan d'entraînement cognitif basé sur les scores et l'objectif utilisateur.

Matrice de recommandation (LOGIQUE STRICTE):
- Concentration < 40 ET Mémoire < 40 → Plan base renforcement
- Concentration 40-70 ET Mémoire > 70 → Plan optimisation focus
- Concentration > 70 ET Mémoire < 40 → Plan amélioration mémoire
- Concentration > 70 ET Mémoire > 70 → Plan entraînement avancé
"""
from typing import List
from .models import (
    ObjectiveEnum, 
    CognitiveProfile, 
    RecommendationPlan, 
    RecommendationItem
)


def get_base_activities(objective: ObjectiveEnum) -> List[RecommendationItem]:
    """
    Retourne les activités de base selon l'objectif utilisateur.
    
    Args:
        objective: Objectif choisi par l'utilisateur
        
    Returns:
        Liste d'activités recommandées
    """
    activities = []
    
    if objective == ObjectiveEnum.ACADEMIC:
        activities = [
            RecommendationItem(
                activity="Pomodoro Adaptatif",
                frequency="Quotidien",
                duration="25/5 min",
                tools=["Timer", "Application Pomodoro"],
                description="Cycles de travail focalisé avec pauses courtes pour optimiser la rétention."
            ),
            RecommendationItem(
                activity="Spaced Repetition (Anki)",
                frequency="Quotidien",
                duration="20-30 min",
                tools=["Anki", "Flashcards"],
                description="Révision espacée pour consolider la mémoire à long terme."
            )
        ]
    elif objective == ObjectiveEnum.PROFESSIONAL:
        activities = [
            RecommendationItem(
                activity="Deep Work Sessions",
                frequency="5x/semaine",
                duration="50/10 min",
                tools=["Bloc-notes", "Timer"],
                description="Sessions de travail profond sans distraction pour la productivité."
            ),
            RecommendationItem(
                activity="Priorisation Eisenhower",
                frequency="Hebdomadaire",
                duration="15 min",
                tools=["Matrice Eisenhower"],
                description="Classer les tâches par urgence et importance."
            )
        ]
    elif objective == ObjectiveEnum.WELLNESS:
        activities = [
            RecommendationItem(
                activity="Respiration 4-7-8",
                frequency="2x/jour",
                duration="5 min",
                tools=["Aucun"],
                description="Technique de respiration pour réduire le stress et améliorer le focus."
            ),
            RecommendationItem(
                activity="Mindfulness Méditation",
                frequency="Quotidien",
                duration="10-15 min",
                tools=["Application méditation"],
                description="Pleine conscience pour améliorer la concentration et réduire l'anxiété."
            )
        ]
    else:  # TRAINING
        activities = [
            RecommendationItem(
                activity="N-Back Training",
                frequency="3x/semaine",
                duration="15-20 min",
                tools=["Application N-Back"],
                description="Entraînement adaptatif de la mémoire de travail."
            ),
            RecommendationItem(
                activity="Dual-Task Exercises",
                frequency="2x/semaine",
                duration="20 min",
                tools=["Chronomètre"],
                description="Exercices combinant deux tâches cognitives simultanément."
            )
        ]
    
    return activities


def generate_recommendation_plan(
    concentration_score: float,
    memory_score: float,
    profile: str,
    objective: ObjectiveEnum
) -> RecommendationPlan:
    """
    Génère un plan de recommandation personnalisé selon la matrice stricte.
    
    Args:
        concentration_score: Score de concentration (0-100)
        memory_score: Score de mémoire (0-100)
        profile: Profil cognitif identifié
        objective: Objectif utilisateur
        
    Returns:
        Plan de recommandation complet
    """
    activities: List[RecommendationItem] = []
    progress_tracking = ""
    retest_days = 30
    
    # ==================== MATRICE DE DÉCISION ====================
    
    # Cas 1: Concentration < 40 ET Mémoire < 40
    if concentration_score < 40 and memory_score < 40:
        activities = [
            RecommendationItem(
                activity="Pomodoro 15/5",
                frequency="Quotidien",
                duration="15/5 min",
                tools=["Timer"],
                description="Cycles courts pour reconstruire progressivement la concentration."
            ),
            RecommendationItem(
                activity="Spaced Repetition (Anki)",
                frequency="Quotidien",
                duration="15-20 min",
                tools=["Anki"],
                description="Renforcement de la mémoire par répétition espacée."
            ),
            RecommendationItem(
                activity="Hygiène du Sommeil",
                frequency="Quotidien",
                duration="8h/nuit",
                tools=["Tracker sommeil"],
                description="Le sommeil est crucial pour la consolidation mnésique et la récupération cognitive."
            ),
            RecommendationItem(
                activity="N-Back Niveau 1-2",
                frequency="2x/semaine",
                duration="10 min",
                tools=["Application N-Back"],
                description="Entraînement léger de la mémoire de travail."
            )
        ]
        progress_tracking = "Re-test à J+15. Objectif: +10 points sur chaque score."
        retest_days = 15
    
    # Cas 2: Concentration 40-70 ET Mémoire > 70
    elif 40 <= concentration_score <= 70 and memory_score > 70:
        activities = [
            RecommendationItem(
                activity="Deep Work 50/10",
                frequency="5x/semaine",
                duration="50/10 min",
                tools=["Timer", "Bloc-notes"],
                description="Sessions de travail profond pour exploiter votre excellente mémoire."
            ),
            RecommendationItem(
                activity="Matrice Eisenhower",
                frequency="Hebdomadaire",
                duration="15 min",
                tools=["Template Eisenhower"],
                description="Optimisez votre productivité en priorisant efficacement."
            ),
            RecommendationItem(
                activity="Cardio Modéré",
                frequency="3x/semaine",
                duration="30 min",
                tools=["Aucun"],
                description="L'exercice cardio améliore l'oxygénation cérébrale et la concentration."
            )
        ]
        progress_tracking = "Re-test à J+30. Objectif: Maintenir mémoire > 70, viser concentration > 70."
    
    # Cas 3: Concentration > 70 ET Mémoire < 40
    elif concentration_score > 70 and memory_score < 40:
        activities = [
            RecommendationItem(
                activity="Palais Mental (Method of Loci)",
                frequency="3x/semaine",
                duration="20 min",
                tools=["Guide palais mental"],
                description="Technique antique pour améliorer significativement la mémoire spatiale."
            ),
            RecommendationItem(
                activity="Rappel Différé Progressif",
                frequency="Quotidien",
                duration="15 min",
                tools=["Listes de mots"],
                description="Entraînement du rappel après des délais croissants."
            ),
            RecommendationItem(
                activity="Respiration 4-7-8",
                frequency="2x/jour",
                duration="5 min",
                tools=["Aucun"],
                description="Technique de relaxation pour optimiser l'encodage mnésique."
            ),
            RecommendationItem(
                activity="Hygiène du Sommeil Renforcée",
                frequency="Quotidien",
                duration="8-9h/nuit",
                tools=["Tracker sommeil"],
                description="Le sommeil paradoxal est essentiel pour la consolidation mémorielle."
            )
        ]
        progress_tracking = "Re-test à J+20. Objectif: +15 points mémoire, maintenir concentration > 70."
        retest_days = 20
    
    # Cas 4: Concentration > 70 ET Mémoire > 70
    elif concentration_score > 70 and memory_score > 70:
        activities = [
            RecommendationItem(
                activity="Entraînement Croisé (Dual-Task)",
                frequency="3x/semaine",
                duration="25 min",
                tools=["Applications cognitives"],
                description="Combinez plusieurs tâches pour challenger vos capacités déjà élevées."
            ),
            RecommendationItem(
                activity="Stroop Test Avancé",
                frequency="2x/semaine",
                duration="15 min",
                tools=["Test Stroop"],
                description="Améliorez votre contrôle inhibiteur et flexibilité cognitive."
            ),
            RecommendationItem(
                activity="N-Back Niveau 3+",
                frequency="3x/semaine",
                duration="20 min",
                tools=["Application N-Back avancée"],
                description="Maintenez vos performances avec des défis progressifs."
            ),
            RecommendationItem(
                activity="Suivi Hebdomadaire",
                frequency="Hebdomadaire",
                duration="10 min",
                tools=["Journal cognitif"],
                description="Auto-évaluation régulière pour détecter toute variabilité."
            )
        ]
        progress_tracking = "Re-test à J+45. Objectif: Maintenir les deux scores > 70, réduire la variabilité."
        retest_days = 45
    
    # Cas par défaut (entre-deux)
    else:
        activities = get_base_activities(objective)
        activities.append(
            RecommendationItem(
                activity="N-Back Progressif",
                frequency="2x/semaine",
                duration="15 min",
                tools=["Application N-Back"],
                description="Entraînement adaptatif pour équilibrer concentration et mémoire."
            )
        )
        progress_tracking = "Re-test à J+30. Objectif: Identifier votre profil dominant."
    
    # Ajouter les activités spécifiques à l'objectif si non déjà incluses
    base_obj_activities = get_base_activities(objective)
    existing_activity_names = {a.activity for a in activities}
    
    for act in base_obj_activities:
        if act.activity not in existing_activity_names:
            activities.append(act)
    
    return RecommendationPlan(
        profile=CognitiveProfile(profile),
        concentration_score=concentration_score,
        memory_score=memory_score,
        activities=activities,
        retest_days=retest_days,
        progress_tracking=progress_tracking
    )
