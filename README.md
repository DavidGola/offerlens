# offerlens

**Lentille intelligente sur les offres d'emploi — scoring personnalisé via RAG sur ton CV.**

`offerlens` scanne quotidiennement des offres d'emploi (Indeed, France Travail, URLs collées), les note contre ton profil grâce à un pipeline LangChain + RAG, et t'envoie un digest matinal Gmail avec le top 5 + explications.

## Statut

🟡 **Pré-MVP — Phase de spécification terminée, implémentation Sprint 1 à démarrer.**

Toutes les décisions structurantes sont prises et documentées dans [`docs/DECISIONS.md`](docs/DECISIONS.md).

## Le problème

En recherche d'emploi active, le bottleneck n'est ni la rédaction du CV ni la prep entretien — c'est **filtrer le bruit** dans le flot d'offres quotidiennes. Les filtres traditionnels (mots-clés, ville, salaire) sont trop rigides et laissent passer 80% d'offres non pertinentes.

`offerlens` résout ça avec un agent qui **comprend ton CV en profondeur** et raisonne offre par offre.

## Stack en un coup d'œil

| Couche | Choix |
|---|---|
| LLM raisonnement | Claude Haiku 4.5 (swappable via LangChain) |
| Embeddings | Vertex AI `text-embedding-005` |
| Vector store + DB | Firestore native vector search |
| Compute | Cloud Run Job + Cloud Scheduler |
| Output | CLI + Gmail API (digest matinal) |
| Sources | Indeed MCP + France Travail API + URL paste |
| Observabilité | LangSmith (tracing + eval) |

Détails complets dans [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Documentation

- 📐 [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — architecture technique détaillée
- 📋 [`docs/DECISIONS.md`](docs/DECISIONS.md) — toutes les décisions verrouillées avec rationale
- 🏃 [`docs/SPRINT-1.md`](docs/SPRINT-1.md) — backlog ordonné du MVP (1 semaine)
- ⚙️ [`docs/SETUP.md`](docs/SETUP.md) — prérequis et initialisation GCP
- 🧪 [`docs/EVAL.md`](docs/EVAL.md) — stratégie d'évaluation (golden set + LangSmith)

## Vision V2 (post-MVP)

- Mode adaptation CV par offre (réorganisation, jamais d'invention)
- Adapter France Travail (OAuth2)
- LLM-as-judge sur les explications de scoring
- Démo enregistrée pour le portfolio

## Licence

À définir avant publication.

## Auteur

David Gola — en recherche active d'un poste Python Backend / AI Engineer (2026).
