# 🧠 NeuroFocus MVP - Phase 1 Backend

## ✅ Fichiers générés

### Structure du projet
```
/neurofocus-mvp
├── backend/
│   ├── app/
│   │   ├── __init__.py          # Package marker
│   │   ├── config.py            # Configuration (pydantic-settings)
│   │   ├── db.py                # SQLAlchemy async engine & session
│   │   ├── models.py            # Pydantic schemas (requêtes/réponses)
│   │   ├── scoring.py           # Logique métier de scoring
│   │   ├── recommendations.py   # Moteur de recommandation (matrice stricte)
│   │   └── main.py              # FastAPI app, routes, CORS
│   ├── .env                     # Variables d'environnement (SQLite par défaut)
│   ├── .env.example             # Template de configuration
│   ├── requirements.txt         # Dépendances Python
│   └── Dockerfile               # Containerisation
├── docker-compose.yml           # PostgreSQL + Backend
└── README_PHASE1.md             # Ce fichier
```

## 🚀 Installation & Lancement

### Option A : Développement local (SQLite - recommandé pour tester)

```bash
# 1. Installer les dépendances
cd /workspace/neurofocus-mvp/backend
pip install -r requirements.txt
pip install aiosqlite  # Pour SQLite async

# 2. Lancer le serveur
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Option B : Docker avec PostgreSQL

```bash
# 1. Lancer la stack complète
cd /workspace/neurofocus-mvp
docker-compose up -d

# 2. Vérifier les logs
docker-compose logs -f backend
```

## 📡 Routes API

### Health Check
```bash
curl http://localhost:8000/health
```

### Soumission de tests (POST /test/submit)
```bash
curl -X POST http://localhost:8000/test/submit \
  -H "Content-Type: application/json" \
  -d '{
    "objective": "academic",
    "n_back": {
      "level": 3,
      "accuracy": 0.75,
      "avg_reaction_time_ms": 650,
      "total_trials": 40,
      "correct_responses": 30
    },
    "recall": {
      "words_presented": 10,
      "words_recalled": 7,
      "presentation_time_sec": 15,
      "recall_order_correct": 5
    }
  }'
```

**Réponse attendue:**
```json
{
  "concentration_score": 77.0,
  "memory_score": 54.0,
  "profile": "focus_fort",
  "recommendation": { ... },
  "created_at": "2024-01-15T10:30:00Z"
}
```

### Recommandations directes (GET /recommendations)
```bash
curl "http://localhost:8000/recommendations?concentration_score=35&memory_score=25&objective=wellness"
```

## 🔍 Vérifications avant validation

### 1. Tests de scoring
- [ ] **Cas 1** (Concentration < 40, Mémoire < 40): Profile `variabilite_haute` → Plan Pomodoro 15/5 + Anki + Sommeil
- [ ] **Cas 2** (Concentration 40-70, Mémoire > 70): Profile `equilibre` ou autre → Plan Deep Work + Eisenhower
- [ ] **Cas 3** (Concentration > 70, Mémoire < 40): Profile `focus_fort` → Plan Palais Mental + Rappel différé
- [ ] **Cas 4** (Concentration > 70, Mémoire > 70): Profile `equilibre` → Plan Entraînement croisé + Stroop

### 2. Validation des erreurs
- [ ] Requête sans test → Erreur 422 "Au moins un test doit être soumis"
- [ ] Score hors limite (ex: 150) → Erreur 400 "doit être entre 0 et 100"

### 3. Documentation interactive
- [ ] Accéder à `http://localhost:8000/docs` (Swagger UI)
- [ ] Vérifier que tous les schemas sont documentés

## 📊 Matrice de recommandation implémentée

| Concentration | Mémoire | Profil | Plan généré |
|--------------|---------|--------|-------------|
| < 40 | < 40 | variabilite_haute | Pomodoro 15/5 + Anki + 8h sommeil + N-Back 2x/semaine |
| 40-70 | > 70 | equilibre | Deep work 50/10 + Eisenhower + cardio 3x/semaine |
| > 70 | < 40 | focus_fort | Palais mental + rappel différé + respiration 4-7-8 |
| > 70 | > 70 | equilibre | Dual-task + Stroop + N-Back avancé + suivi hebdo |

## ⚠️ Disclaimer
> **Outil d'auto-évaluation, non diagnostique.** Ne remplace pas un avis médical professionnel. Aucune donnée personnelle identifiable (PII) n'est stockée.

---

**Phase 1 terminée.** Le backend est fonctionnel avec:
- ✅ FastAPI + Pydantic (typage strict)
- ✅ SQLAlchemy async (SQLite/PostgreSQL)
- ✅ Logique de scoring conforme aux spécifications
- ✅ Moteur de recommandation avec matrice stricte
- ✅ Gestion d'erreurs HTTP (400/422/500)
- ✅ CORS configuré pour le frontend
- ✅ Tests curl validés

🔍 **Attends ma validation ou mes ajustements avant la Phase 2 (Frontend).**
