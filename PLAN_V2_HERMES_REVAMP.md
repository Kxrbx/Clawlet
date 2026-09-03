# Clawlet v2 — Plan Revamp complet (inspiration Hermes)

> **État d'implémentation (branche `v2-hermes-revamp`) :** P0 ✅ · P1 ✅ · Orchestrateur ✅ · P2 ✅ · P3 ✅ · P4 ✅ (index skills + docs ; boucle de consolidation mémoire auto → suivi) · **Desktop exclu du périmètre sur demande (reporté)**. 101 tests verts, smoke release OK.

> **Décisions figées :** nom `Clawlet` conservé · même repo `Kxrbx/Clawlet`, branche `v2-hermes-revamp` · full-break autorisé (Python ≥3.11, deps optionnelles, dashboard refonte autorisée) · priorités P1 One-loop+registry, P2 SessionDB+perfs, P3 Skills+mémoire auto · orchestrateur systématique · Desktop Tauri 2 + React full-admin.
> **Hors-scope v2.0 (backlog v2.1) :** gateway 30+ plateformes, kanban-swarm multi-agents, cron langage naturel.

---

## 1. Constat — audit actuel

### 1.1 Structure

| Module | Rôle | Fichiers clés / taille |
|---|---|---|
| `clawlet/agent/` (22 f.) | Cœur agent | `loop.py:2609l`, `memory.py:907l`, `run_orchestrator.py`, `turn_executor.py:645l`, `message_builder.py`, `tool_parser.py`, `router.py:300l`, `workspace.py:678l` |
| `clawlet/providers/` (19 f.) | 16 LLM + base + cache | `base.py:232l`, `openrouter.py:296l`, 10x OpenAI-compat ~180l chacun, `models_cache.py:114l` |
| `clawlet/tools/` (12 f.) | Registry + outils | `registry.py:276l`, `files.py:393l`, `shell.py:434l`, `http_request.py:438l`, `web_search.py:239l`, `memory.py:430l`, `notes.py:475l` |
| `clawlet/runtime/` (14 f.) | Runtime déterministe v2 | `executor.py`, `replay.py`, `recovery.py`, `policy.py`, `rust_bridge.py:184l` (mort) |
| `clawlet/channels/` (10 f.) | Telegram/Discord/Slack/WhatsApp | `telegram.py:787l`, `slack.py:713l`, `discord.py:317l`, `whatsapp.py:470l` |
| `clawlet/heartbeat/` (7 f.) | Boucle autonome | `cron_scheduler.py:1242l`, `runner.py`, `scheduler.py`, `state.py` |
| `clawlet/storage/` | Conversations | `sqlite.py` (`store_message/get_messages`), `postgres.py:351l` (`add_message/get_history` — API divergente) |
| `clawlet/context/` (5 f.) | Indexation workspace | `engine.py`, `indexer.py`, `retriever.py` |
| `clawlet/skills/`, `clawlet/plugins/` | Skills `SKILL.md`, SDK v2 | `sdk.py` (`NotImplemented`), `loader.py` |
| `clawlet/cli/` (28 f.) | CLI Typer `clawlet` | `onboard.py:1074l`, `runtime_ui.py:550l`, `__init__.py:422l` |
| `clawlet/tui/` | TUI textual | `app.py:142l`, `controller.py`, `state.py` |
| `clawlet/dashboard/` | Backend FastAPI | `api.py:698l` |
| `clawlet/benchmarks/` (15 f.) | Gates perf | `runner.py`, `release_gate.py`, `corpus.py:507l` |
| `dashboard/` | Frontend React19+Vite7+Tailwind4 | `src/App.tsx:31KB`, `hooks/useClawletAPI.ts`, `recharts`, `react-query` |
| Transverse | Config/sécu/ops | `config.py:854l`, `exceptions.py:311l`, `health.py:473l`, `retry.py`, `workspace_layout.py:105l` |

### 1.2 Dette bloquante

* **God objects :** `loop.py`, `cron_scheduler.py`, `onboard.py`, `memory.py`, `telegram.py/slack.py`.
* **Duplication :** 10-12 providers OpenAI-compat copié-collés ; 16x `*Config` identiques ; 2x `RateLimiter` (`rate_limit.py` vs `tools/registry.py:17-40`) ; `requirements*.txt` vs `pyproject.toml` vs `requirements-core/dev.txt` désync (ex. `tenacity` que dans core).
* **Couplage :** `AgentLoop.__init__` construit tout (SQLite/Postgres, MemoryManager, EventStore, PolicyEngine, ToolRuntime, ContextEngine, RecoveryManager) — pas d'injection. `HTTPClientManager` singleton illusoire (client recréé par provider). `storage` : fallback `hasattr` dans `loop.py`.
* **Mort :** `rust_bridge.py` (config normalise déjà `hybrid_rust→python`), `plugins/sdk.py` vide.
* **Deps lourdes obligatoires :** `textual, python-telegram-bot, discord.py, slack_bolt, twilio` (~200MB même en local-only). `Dockerfile` incohérent (`USER clawlet` mais `PATH=/root/.local`).
* **Tests :** ~58 `def test_*`, <15% modules, concentrés `rate_limit/memory/sqlite/shell/provider_base/tui/circuit_breaker/config_reload/architecture_guards`. Zéro test 15/16 providers réels, channels, heartbeat, webhooks, dashboard, onboard, skills, runtime replay/remote.
* **Version :** `pyproject.toml:0.5.0` vs `clawlet/__init__.py:0.4.7` désync.

### 1.3 Ce qu'on vole à Hermes (Nous Research)

* **One loop, many surfaces :** `AIAgent.run_conversation()` unique ; CLI/gateway/cron/kanban = wrappers fins. Pas de `core/framework` abstrait.
* **Registry outils :** 1 fichier = 1 outil, `registry.register()` au load, tout passe par `handle_function_call` (coercition JSON, hooks pre/post, approvals). Pas de hiérarchie décorateur dispersée.
* **Toolsets :** bundles `minimal/coding/full` + `check_fn`, presets `terminal,browser`.
* **SessionDB :** 1 SQLite WAL + FTS5 = vérité (sessions, messages, `parent_session_id`, `source`, colonne `system_prompt`).
* **Prompt 3 tiers + cache :** stable build-once + `_cached_system_prompt` invalidé après compression ; volatile injecté à l'appel. Index skills ~630 tokens, contenu on-demand (progressive disclosure).
* **Sub-agents = fresh instances :** même init path, budget/tools isolés, retour résumé. Profondeur max 1.
* **Cold-start :** lazy-install backends, `--version`/`tools` <1.5s, compression 2-seuils incrémentale, `session_search` FTS sans LLM (~20ms vs ~30s).
* **Self-improve :** consolidation horaire, distillation skills quotidienne, curator hebdo, meta-éval (retry/erreur/overflow).
* **Desktop :** même core/config/sessions que CLI, shell Tauri/Electron + backend headless `serve` JSON-RPC/WS, contrat versionné, self-update, plugins ESM.

---

## 2. Cible v2 — principes

1. **Une boucle, un registry, une SessionDB.** `loop.py` devient forwarder <300l.
2. **Orchestrateur toujours.** Aucune requête non-triviale ne touche les outils sans passer par `classify → spawn(kind) → synthesize`.
3. **Pluggable at the edges, fixed in the middle.** Boucle, registry, SessionDB, modèle session non-négociables ; tools/platforms/sandboxes/providers/skills en registry.
4. **Opt-in context.** Skills slash-invoquées, jamais auto-chargées en masse.
5. **Perfs d'abord.** Core léger, tout ce qui est lourd en extra lazy.
6. **Secrets hors historique.** `clawlet config set TOKEN` → `.env`, jamais dans SessionDB/transcripts.

---

## 3. Phase 0 — Branche + hygiène (0.5j)

* `git checkout -b v2-hermes-revamp` depuis `main` (`d10a52d`).
* Version → `0.6.0a0` partout (`pyproject.toml`, `clawlet/__init__.py`, `dashboard/api.py`, README).
* `requires-python >= 3.11`, `ruff` + `black` en CI, `coverage` introduit sans seuil bloquant puis ` --fail-under=40` cœur.
* Suppressions immédiates : `runtime/rust_bridge.py`, `plugins/sdk.py` (ou implémentation minimale), legacy `hybrid_rust`, `benchmark equivalence` restes.
* Vérif : `pytest --collect-only`, `python scripts/release_smoke.py`.

---

## 4. Phase 1 — One-loop + Tool Registry + Toolsets (3-5j, P1)

### 4.1 Fichiers

* Nouveau `clawlet/agent/conversation_loop.py` : boucle extraite de `loop.py`/`turn_executor.py`.
* Nouveau `clawlet/agent/agent_init.py` : credentials, allowlists, `IterationBudget`, compression settings.
* Nouveau `clawlet/agent/system_prompt.py` : prompt 3 tiers (stable/volatile/contexte), cache + `invalidate_system_prompt()`.
* Nouveau `clawlet/run_agent.py` : façade `AIAgent.run_conversation()` (CLI/gateway/cron appellent ici).
* `clawlet/agent/loop.py` : forwarder fin + guards `clawlet/tests/unit/test_architecture_guards.py` étendus (interdire re-grossissement >300l).
* `clawlet/tools/registry.py` → pattern Hermes : `register()` par fichier, suppression doublon `RateLimiter`.
* Nouveau `clawlet/tools/model_tools.py` : `handle_function_call` central (coercition, `tool_search/tool_describe/tool_call` bridge, hooks, approval gates).
* Nouveau `clawlet/tools/toolsets.py` : `minimal/coding/full/memory-only/browser`, `check_fn`, presets CLI `--toolsets coding,browser`.
* `approval_service.py` existant → pre-tool hooks (commandes dangereuses, edit hors scope, exfiltration), délimiteurs résultats anti-promptware.
* CLI : `clawlet tools` (<1.5s), `clawlet --version` rapide.

### 4.2 Providers (inclus P1)

* Nouvelle `OpenAICompatibleBase` : 1 classe pour les 10-12 providers quasi-identiques (`minimax, moonshot, qwen, zai, copilot, vercel, opencode_zen, xiaomi, synthetic, venice`) — seules `BASE_URL/default_model` changent.
* `config.py` : `APIKeyConfig` de base déjà partiellement fait en `0.2.3` → généraliser aux 16 configs.
* `HTTPClientManager` : vrai pool `httpx.AsyncClient` partagé, suppression accès privé `manager._client._limits`.
* `mask_secrets` : tous providers (actuellement que OpenRouter).
* Vérif : tests registry/toolsets/approvals, `pytest tests/unit`, gate `release_gate.py`.

---

## 5. Phase 2 — SessionDB + Storage unique + Compression (2-3j, P2)

* Nouveau `clawlet/storage/session_db.py` : `SessionDB` WAL + FTS5, schéma v1 :
  `sessions(id, parent_session_id, task_kind, profile_snapshot, system_prompt, source, created_at)`,
  `messages(id, session_id, role, content, tool_name, created_at)` + index FTS.
* Remplace `sqlite.py`/`postgres.py` divergents. Postgres → extra optionnel ou drop v2 (recommandé : garder interface `StorageBackend` fine qui délègue à SessionDB, `asyncpg` en extra).
* Fusion `memory.db` + `clawlet.db` → SessionDB + `MEMORY.md` projection + `memory/YYYY-MM-DD.md` (garder API `remember/append_note/search/review/curate/memory_status` mais sur SessionDB, FTS prioritaire puis `LIKE`).
* Nouveau `clawlet/agent/context_manager.py` : compression 2-seuils (head protégée / middle résumable / tail récente, placeholders >200c, résumé incrémental 20% budget 2K-12K, mise à jour du résumé précédent au lieu de régénérer).
* Prompt cache : `_cached_system_prompt` + snapshot frozen `MEMORY.md+USER.md` (prefix-caching Anthropic).
* `session_search` FTS trigram sans LLM auxiliaire.
* Vérif : tests reload recent-first, metadata round-trip, trim répété, FTS, resume fidélité, `review_daily_notes`.

---

## 6. Phase 3 — Perfs cold-start + Deps optionnelles (2j, P2)

`pyproject.toml` cible :

```toml
dependencies = [pydantic, PyYAML, loguru, httpx, typer, rich, questionary, fastapi, uvicorn, aiosqlite, croniter]
[project.optional-dependencies]
channels-telegram = ["python-telegram-bot"]
channels-discord  = ["discord.py"]
channels-slack    = ["slack_bolt"]
channels-whatsapp = ["twilio"]
local-ollama      = []
tui               = ["textual"]
monitoring        = ["psutil"]
postgres          = ["asyncpg"]
providers-openai  = ["openai"]
providers-anthropic = ["anthropic"]
```

* Lazy-import généralisé (étendre pattern `clawlet/__init__.py:__getattr__`). `textual`, channels, `openai/anthropic` SDKs chargés à l'usage avec message d'install + advisory.
* `cli/onboard.py:1074l` découpé (steps provider/config/identity/workspace/tasks), `textual` TUI → extra.
* `models_cache` refresh quotidien non-bloquant + `--offline`.
* Secrets : `clawlet config set GITHUB_TOKEN xxx` écrit hors historique (modèle Hermes `/opt/data.env`), dashboard bind `127.0.0.1` + token requis par défaut.
* Objectifs chiffrés : `clawlet --version` -63%, `clawlet tools` <1.5s, -40% calls/turn (mesuré `benchmarks/` sur conversation 31 tours), `browser` outil ~180x via CDP persistant (si repris).
* Vérif : `benchmarks/release_gate.py`, `release_regression.py`, mesure cold-start en CI.

---

## 7. Phase 4 — Skills progressive disclosure + mémoire auto (2-3j, P3)

* Skills : front-matter YAML obligatoire (`name, description, triggers, tools`), index titres+descriptions (~630 tokens pour 50 skills), `skills_list/skill_view/skill_manage` + bridge `tool_search/tool_describe/tool_call`. Sources : `skills/`, `optional-skills/`, `~/.clawlet/skills/`.
* Distillation : post-task (5+ tool calls / recovery / correction utilisateur) propose `SKILL.md` ; curator hebdo note/déduplique/élague (anti-cimetière).
* Mémoire : consolidation horaire (prefs stables → SQLite, projection `MEMORY.md` incrémentale — plus de réécriture complète `save_long_term()`), `USER.md` <500 tokens + `MEMORY.md` <800 tokens frozen en tête pour caching.
* Boucles lentes async (jamais synchrones fin-de-session) : L6 consolidation heure, L7 distillation jour, L8 meta-éval jour (retry rate, taux erreur outil, overflow → rapport + reco seuils).
* Docs : réécriture `ARCHITECTURE.md` (One loop/many surfaces, registry, SessionDB, toolsets, orchestrateur), `docs/runtime-v2.md`, `QUICKSTART.md`, `DEPLOYMENT.md`, `OPERATIONS.md`. Supprimer références design pré-Hermes.
* Vérif : tests disclosure (budget tokens), distillation, curator, consolidation ; `pytest -m "unit or integration"`.

---

## 8. Phase 5 — Orchestrateur systématique + sous-agents configurables

> Acté : délégation par défaut + fallback · taxonomie fixe + surchargeable · classification hybride · profil complet + héritage.

### 8.1 Écart actuel

`router.py` route `channel/user/pattern → workspace`, pas `requête → task-kind → sous-agent`. `run_orchestrator.py` prépare `RunContext` puis appelle `_process_message_core` (pas de spawn). `turn_executor.py` exécute provider+tools inline. `config.py` n'a qu'un `provider.primary` global. Zéro `delegate_task`/`IterationBudget`.

### 8.2 Flux cible

```
Inbound → Orchestrator (modèle cheap, 0-5 iters, tools OFF)
  → TaskRouter hybride → task-kind
  → SubAgentFactory.spawn(kind) : fresh AIAgent, profil résolu, historique propre, row enfant
  → exécution isolée (×N si fan-out research) → résumé typé → Orchestrateur synthétise → outbound
```

Orchestrateur = routage + synthèse uniquement. Fallback direct seulement si trivial (salutation, <200 chars, pas d'action-intent) ou confiance basse + urgence → tracé `fallback:true`.

### 8.3 Config par tâche

```yaml
orchestrator:
  model: {provider: openrouter, model: anthropic/claude-haiku-4}
  max_iterations: 5
  allow_direct_fallback: true
  trivial_max_chars: 200
  classifier: {mode: hybrid, llm_profile: router-cheap, timeout_s: 5, cache_ttl_s: 300}
  max_parallel_subagents: 3
  max_depth: 1

task_profiles:
  code:     {provider: anthropic, model: claude-sonnet-5-20260203, toolset: coding, max_iterations: 50, tool_call_limit: 20, timeout_s: 180, temperature: 0.2}
  plan:     {provider: openai, model: gpt-5, toolset: minimal, max_iterations: 15, timeout_s: 90, temperature: 0.3}
  research: {provider: openrouter, model: gemini-4-pro, toolset: browser, max_iterations: 25, timeout_s: 120}
  browser:  {provider: openrouter, model: gemini-4-pro, toolset: browser, max_iterations: 20, timeout_s: 120}
  memory:   {provider: ollama, model: llama3.2, toolset: memory-only, max_iterations: 10}
  review:   {provider: anthropic, model: claude-haiku-4, toolset: minimal, max_iterations: 10}
  ops-tool: {provider: ollama, model: llama3.2, toolset: full, max_iterations: 15}
  chat:     {provider: openrouter, model: anthropic/claude-haiku-4, toolset: minimal, max_iterations: 5}
  defaults: {provider: openrouter, model: anthropic/claude-sonnet-4, toolset: full, fallback: {provider: ollama, model: llama3.2}}
```

Résolution : `task-kind → task_profiles[kind] → defaults → provider.*` global. `clawlet validate` + étape onboard 8 « per-task models » + `clawlet tasks list/show/test-routing "..."`.

### 8.4 Fichiers (ordre)

1. `clawlet/agent/task_profiles.py` (nouveau) : `TaskProfile`, `resolve(kind, config)`, fallback.
2. `clawlet/agent/task_router.py` (nouveau) : `classify(text, history) → (kind, confidence, reason)` — règles sync extraites de `turn_executor.py` (`_is_action_intent`, URL/skill policies) puis micro-classifieur LLM cheap + cache LRU.
3. `clawlet/agent/subagent.py` (nouveau) : `spawn(parent_ctx, kind, instruction)` — fresh `AgentLoop` via `agent_init`, row `parent_session_id`, historique = instruction + slice pertinente (jamais tout `convo.history`), budget/toolset/profil propres.
4. `clawlet/agent/orchestrator.py` (nouveau) : `process_message()` → classify → `spawn` (ou `asyncio.gather(sem)` fan-out `research`) → `synthesize()`. `run_orchestrator.py` gardé comme forwarder.
5. `clawlet/tools/delegate.py` (nouveau, interne non-récursif, `depth` guard — enfants `depth=1` ne redélèguent pas).
6. `SessionDB` : colonnes `parent_session_id, task_kind, profile_snapshot` obligatoires (coûts/traçabilité).
7. Observabilité : `run_id` parent/enfant liés, events `orchestrated/delegated/synthesized`, `replay` compatible. Heartbeat passe aussi par l'orchestrateur (`kind=scheduled`).

### 8.5 Garde-fous

* Coût : 2+ appels LLM/requête → cache routeur, trivial-bypass, synthèse fusionnée au dernier tour worker si single-task.
* Fan-out : seul `research` multi-requêtes en v2, cap 3, timeout global 180s.
* Sécu : enfants héritent `mode/activity` parent, jamais plus permissifs ; `http_auth_profiles` jamais en clair dans l'instruction enfant.
* Vérif : tests résolution/héritage, routeur (règles sans réseau, LLM mocké), isolation spawn, synthèse single/fan-out ; e2e `tasks test-routing` sur 3 profils × 2 providers.

---

## 9. Phase 6 — Clawlet Desktop (Tauri 2 + React, full admin, Hermes-like)

> Acté : **Tauri 2 + React** (binaire ~10MB, updater signé, `safeStorage`, réutilise `dashboard/src/`) · **full admin v1** (chat + orchestrateur + providers + gateway + cron + skills + mémoire).

### 9.1 Architecture

```
apps/desktop/ (Tauri 2 + React TS)
  ├─ src-tauri/ (Rust : lifecycle backend, safeStorage, updater, notifications, shortcuts)
  ├─ src/ (évolution dashboard/src/ : chat, sessions, palette, settings, admin)
  └─ shared/ (client JSON-RPC/WS généré depuis OpenAPI FastAPI)

Backend Python : `clawlet serve --port 0 --token ...`
  = api.py actuel + TUI-runtime (controller/store) + SessionDB + orchestrateur
  expose `tui_gateway` JSON-RPC/WS ; self-contained, jamais besoin du dashboard web.
```

Parité Hermes : même `~/.clawlet/` que CLI (config, keys, sessions, skills, mémoire), backend résolu `CLAWLET_DESKTOP_ROOT → install managée → clawlet sur PATH → override CLAWLET_DESKTOP_CLAWLET`, fallback `dashboard --no-open` si `serve` absent, contrat `CLAWLET_DESKTOP_CONTRACT` avec CTA update si backend trop vieux, logs `~/.clawlet/logs/`, plugins `~/.clawlet/desktop-plugins/plugin.js` hot-reload.

### 9.2 Fonctionnalités v1

* **Chat** : streaming SSE/WS, tool-rows stables + résumés, SessionDB partagée CLI↔Desktop, `/undo` N turns, paste image, drag-drop, rail preview droit (fichiers/pages/outputs), todo widget, timers.
* **Orchestrateur visible** : badge `task-kind`, arbre parent→enfants, profil `provider/model/toolset/budget` affiché, bouton re-router.
* **Sessions multi-profils** : local + remote (URL/SSH, OAuth/token), `Ctrl+1-9`, recherche `Ctrl+Shift+F`, archive.
* **Model picker flou** partout + **par tâche** (`status-bar` défaut + `Settings → Tasks`), écrit via backend `config set` (jamais de secret dans transcripts).
* **Admin** : providers/keys, toolsets, MCP catalog, channels, webhooks, cron `jobs.yaml`, skills (index + install/curate), mémoire, santé/métriques (`health.py`, `metrics.py`), gateway ops.
* **Shell** : palette `Cmd+K`, shortcuts rebindables avec conflits, toggle YOLO per-session (mappe `safe/full_exec` + approvals parité `tui/app.py:121-134`), thèmes, i18n FR/EN.
* Suppression Hermes-parité : flag `dashboard --tui` supprimé (chat toujours intégré).

### 9.3 Phases Desktop

* **D0 socle (2-3j)** : `clawlet/serve.py` headless (token obligatoire, `127.0.0.1`, CORS fermé, `APIRateLimiter` durci), `GET /api/runtime-info {contract:1, version, task_kinds[]}`, WS `/ws/tui_gateway`, client `apps/shared/`, commandes `clawlet serve` + `clawlet desktop`.
* **D1 chat+sessions (1 sem)** : port `dashboard/src` → `apps/desktop/src`, streaming, multi-profils local, palette, picker, file-drop, rail, logs.
* **D2 admin orchestrateur (1 sem)** : UI `task-profiles` CRUD + `test-routing`, arbre sous-agents, providers/toolsets/secrets, skills/cron/mémoire/channels, approvals, thèmes, i18n.
* **D3 packaging (3-5j)** : `src-tauri` (icons, updater, notifications, deep-links), `install.sh/ps1 --include-desktop`, CI mac/linux/win, `Clawlet-Setup.exe --update`, overlay bootstrap venv/deps, self-update `clawlet update`.
* **D4 plugins + durcissement** : SDK `pane/page/palette/keybind/theme`, SSRF off-loop, strip credentials subprocess, secrets `safeStorage` uniquement.

### 9.4 Vérification Desktop

* Contract test golden JSON-RPC, e2e Playwright (new session → stream → tool → approval → switch profile → per-task model change), smoke installateurs 3 OS, updater dry-run.
* Succès : install 1-click → premier message <30s sans YAML, 0 DB séparée, session CLI↔Desktop interchangeable.

---

## 10. Migration v1 → v2 (full-break acté, pas de shim permanent)

* One-shot `scripts/migrate_v1_to_v2.py` : `~/.clawlet/config.yaml` (primary → task_profiles + orchestrator), `clawlet.db` + `memory.db` → SessionDB, `CLAWLET_*` inchangés, `scheduler_state.json`/`cron/` conservés, backup `.bak` + dry-run par défaut.
* `config_migration.py` étendu (matrice + hints `clawlet validate --migration`).
* Dashboard v1 freezé derrière extra si besoin transitoire.

---

## 11. Tests & gates (transverse)

* Unit : registry/toolsets/approvals, SessionDB/FTS/compression/prompt-cache, task-profiles/routeur/spawn/synthèse, serve-contract.
* Intégration : orchestrateur e2e 3 kinds × 2 providers, heartbeat via orchestrateur, Desktop ↔ CLI resume.
* Gates : `pytest`, `pytest --cov --fail-under=40` (cœur), `python scripts/release_smoke.py`, `python scripts/release_regression.py`, `benchmarks/release_gate.py`, cold-start CI, Playwright Desktop.
* Couverture cible : >40% cœur en v2.0 (vs <15% actuel), providers/channels/heartbeat couverts au fil des phases.

---

## 12. Risques & mitigations

| Risque | Mitigation |
|---|---|
| `cron_scheduler.py:1242l` fragile | Inchangé Phases 1-2, refactor après SessionDB + tests ciblés |
| Coût orchestrateur (2+ LLM calls) | Cache routeur, trivial-bypass, synthèse fusionnée |
| Frontend sans tests | Freeze v1 en extra, backend couvert en priorité, Playwright D1 |
| Dérive contrat Desktop↔backend | Integer contrat + CI golden |
| Scope full-admin Desktop trop gros | D1 chat-first flaggé, archi full-admin dès D0 |
| Secrets en renderer/logs | `config set` backend-only, `safeStorage`, `mask_secrets` global, strip subprocess |

---

## 13. Ordre d'exécution recommandé

1. P0 branche + version + suppressions mortes.
2. P1 boucle/registry/toolsets + `OpenAICompatibleBase` + pool HTTP.
3. Orchestrateur (profils + routeur + spawn + synthèse) — utilisable sans SessionDB finale (adaptateur SQLite actuel).
4. P2 SessionDB + compression + prompt-cache (branchement orchestrateur : `parent_session_id/task_kind`).
5. P3 perfs/optionnelles + onboard découpé + `migrate_v1_to_v2.py`.
6. P4 skills/memory-auto + docs `ARCHITECTURE.md` Hermes-first.
7. D0-D4 Desktop.
8. Backlog v2.1 : gateway multi-plateformes (`platforms/base.py`), cron NL, kanban-swarm.

**Critères succès v2.0 :** 1 boucle / 1 registry / 1 SessionDB · `loop.py` <300l · 0 provider dupliqué · 0 `hasattr` storage · 100% non-trivial via `orchestrateur → subagent(kind) → synthèse` loggé · cold-start et coûts en baisse mesurés · smoke+regression+gate verts · Desktop 1-click → premier message <30s.
