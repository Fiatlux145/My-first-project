"""
Module de scoring cognitif.
Implémente les algorithmes de calcul des scores de Concentration et Mémoire
selon les spécifications du MVP NeuroFocus.

Formules:
- Score Concentration (0-100) = (précision N-Back × 50) + (temps réaction inverse normalisé × 30) + (taux erreur CPT simulé × 20)
- Score Mémoire (0-100) = (mots rappelés × 10) + (précision N-Back × 40)
"""
from typing import Optional
from .models import NBackResult, RecallResult


# Constantes de normalisation
MAX_REACTION_TIME_MS = 2000  # Temps de réaction max pour normalisation (2 secondes)
MIN_REACTION_TIME_MS = 200   # Temps de réaction min raisonnable (200ms)


def normalize_reaction_time(reaction_time_ms: float) -> float:
    """
    Normalise le temps de réaction en un score 0-1.
    Plus le temps est court, plus le score est élevé.
    
    Args:
        reaction_time_ms: Temps de réaction moyen en millisecondes
        
    Returns:
        Score normalisé entre 0 et 1
    """
    if reaction_time_ms <= MIN_REACTION_TIME_MS:
        return 1.0
    if reaction_time_ms >= MAX_REACTION_TIME_MS:
        return 0.0
    
    # Inversion: temps court = score haut
    normalized = 1.0 - ((reaction_time_ms - MIN_REACTION_TIME_MS) / 
                        (MAX_REACTION_TIME_MS - MIN_REACTION_TIME_MS))
    return max(0.0, min(1.0, normalized))


def calculate_concentration_score(
    n_back: Optional[NBackResult] = None,
    simulated_cpt_error_rate: float = 0.15
) -> float:
    """
    Calcule le score de Concentration (0-100).
    
    Formule:
    - Précision N-Back × 50 (50% du score)
    - Temps de réaction inverse normalisé × 30 (30% du score)
    - Taux d'erreur CPT simulé inversé × 20 (20% du score)
    
    Args:
        n_back: Résultats du test N-Back (optionnel)
        simulated_cpt_error_rate: Taux d'erreur CPT simulé (0-1), défaut 0.15
        
    Returns:
        Score de concentration entre 0 et 100
    """
    score = 0.0
    components = 0
    
    if n_back is not None:
        # Composante Précision N-Back (50%)
        precision_component = n_back.accuracy * 50.0
        score += precision_component
        
        # Composante Temps de réaction (30%)
        rt_normalized = normalize_reaction_time(n_back.avg_reaction_time_ms)
        rt_component = rt_normalized * 30.0
        score += rt_component
        
        components = 80  # N-Back contribue à 80% du score total
    else:
        # Si pas de N-Back, on utilise uniquement le CPT simulé
        pass
    
    # Composante CPT simulé (20%)
    # Taux d'erreur bas = score haut
    cpt_component = (1.0 - simulated_cpt_error_rate) * 20.0
    score += cpt_component
    
    # Normalisation si seulement CPT est disponible
    if n_back is None:
        score = cpt_component * 5  # Ramener à échelle 0-100
    
    return round(min(100.0, max(0.0, score)), 2)


def calculate_memory_score(
    n_back: Optional[NBackResult] = None,
    recall: Optional[RecallResult] = None
) -> float:
    """
    Calcule le score de Mémoire (0-100).
    
    Formule:
    - Mots rappelés × 10 (max 100 si 10 mots)
    - Précision N-Back × 40 (bonus si N-Back disponible)
    
    Args:
        n_back: Résultats du test N-Back (optionnel)
        recall: Résultats du test Rappel (optionnel)
        
    Returns:
        Score de mémoire entre 0 et 100
    """
    score = 0.0
    
    # Composante Rappel de liste (base)
    if recall is not None:
        # 10 mots × 10 points = 100 max
        recall_component = min(recall.words_recalled, 10) * 10.0
        score += recall_component * 0.6  # 60% du score vient du rappel direct
    
    # Composante N-Back (mémoire de travail)
    if n_back is not None:
        nback_component = n_back.accuracy * 40.0
        if recall is not None:
            nback_component *= 0.4  # 40% restants si rappel présent
        else:
            nback_component *= 2.5  # Pondération plus forte si seul test disponible
        score += nback_component
    
    # Normalisation si aucun test
    if n_back is None and recall is None:
        return 0.0
    
    # Ajustement si seul le rappel est présent
    if n_back is None and recall is not None:
        score = min(recall.words_recalled, 10) * 10.0
    
    return round(min(100.0, max(0.0, score)), 2)


def determine_profile(concentration_score: float, memory_score: float) -> str:
    """
    Détermine le profil cognitif basé sur les scores.
    
    Profils:
    - Équilibré: Les deux scores entre 40-70 ou différence < 15
    - Focus fort: Concentration > 70 et Mémoire < Concentration - 15
    - Mémoire fragile: Mémoire > 70 et Concentration < Mémoire - 15
    - Variabilité haute: Différence > 30 entre les scores
    
    Args:
        concentration_score: Score de concentration (0-100)
        memory_score: Score de mémoire (0-100)
        
    Returns:
        Identifiant du profil (enum string)
    """
    diff = abs(concentration_score - memory_score)
    
    # Variabilité haute: grande différence
    if diff > 30:
        if concentration_score > memory_score:
            return "focus_fort"
        else:
            return "memoire_fragile"
    
    # Focus fort: concentration élevée, mémoire relativement basse
    if concentration_score > 70 and memory_score < concentration_score - 10:
        return "focus_fort"
    
    # Mémoire fragile: mémoire élevée, concentration relativement basse
    if memory_score > 70 and concentration_score < memory_score - 10:
        return "memoire_fragile"
    
    # Cas de faiblesse générale
    if concentration_score < 40 and memory_score < 40:
        return "variabilite_haute"
    
    # Défaut: équilibré
    return "equilibre"


def calculate_all_scores(
    n_back: Optional[NBackResult] = None,
    recall: Optional[RecallResult] = None,
    simulated_cpt_error_rate: float = 0.15
) -> dict:
    """
    Calcule tous les scores et détermine le profil.
    
    Args:
        n_back: Résultats du test N-Back
        recall: Résultats du test Rappel
        simulated_cpt_error_rate: Taux d'erreur CPT simulé
        
    Returns:
        Dictionnaire avec concentration_score, memory_score, et profile
    """
    concentration = calculate_concentration_score(n_back, simulated_cpt_error_rate)
    memory = calculate_memory_score(n_back, recall)
    profile = determine_profile(concentration, memory)
    
    return {
        "concentration_score": concentration,
        "memory_score": memory,
        "profile": profile
    }
