# Assistant and document search

## Principle

The database is the source of truth. The assistant only reads it through a fixed set of tools and writes an answer from what those tools return. It never calls an external service for data and never decides an emergency action.

## Flow

```text
question ──> intent / LLM tool choice ──> tools (SQL, PostGIS, document search) ──> answer
                                                   │
                                                   └──> sources with data class and timestamp
```

1. `POST /api/assistant` receives `question` and `audience` (`ejecutivo`, `tecnico`, `vecino`).
2. **With an LLM configured** (`LLM_BASE_URL`, `LLM_MODEL`): the backend sends the system prompt (rules below), the question and the tool specs to an OpenAI-compatible `/chat/completions` endpoint. Up to four tool rounds. If the model answers without calling any tool, its text is discarded and the deterministic answer is returned instead. If the endpoint fails, the deterministic answer is returned with a notice.
3. **Without an LLM** (default): Spanish keyword intents select up to three tools and a template composes the answer from their output. Same tools, same sources.
4. In both modes the **source list is built by the server from tool outputs**, not by the model, so citations cannot be invented.

## Tools (`backend/app/ai/tools.py`)

| Tool | Retrieval | Returns |
|---|---|---|
| `situacion_actual` | structured | AHORA assessments, alerts entered with official link, alert-feed limitation |
| `riesgo_por_amenaza` | spatial | RIESGO assessments with evidence and exposure |
| `sectores_prioritarios` | spatial | sectors or analysis cells ranked by derived level |
| `infraestructura_expuesta` | spatial | schools, health facilities, municipal assets inside hazard zones |
| `estadisticas` | structured | municipal incidents, earthquakes per year, ICFSR |
| `buscar_documentos` | semantic / lexical | chunks from municipal documents with title and page |
| `fuentes` | structured | source status and last update |

## Rules in the system prompt

Only data from tools; never invent alerts, numbers, places or names; always state the data class; derived levels are platform calculations, not official assessments; never present a forecast as an observation; absence of an alert is not absence of danger; no emergency decisions on behalf of authorities; include update times; cite document title and page.

## Document search (RAG)

- Upload of PDF, TXT or MD under "Datos municipales" → text extracted with pypdf → chunks of about 1,200 characters with 150 characters of overlap, keeping the page number.
- **Default retrieval: PostgreSQL full-text search** with the `spanish` configuration (`websearch_to_tsquery`, then an OR of significant terms as fallback). Works on any installation, no model needed.
- **Optional vector retrieval**: when the `vector` extension exists (the Docker image installs pgvector) and `EMBEDDING_BASE_URL` / `EMBEDDING_MODEL` point to an OpenAI-compatible `/embeddings` endpoint, chunks are embedded at upload and queries combine both result sets.
- Scanned PDFs without OCR produce no text and the upload fails with that message.
- Every query is filtered by `municipality_id`.

## Providers

Any OpenAI-compatible endpoint: Ollama (`http://ollama:11434/v1`, enable with `docker compose --profile local-llm up -d`), llama.cpp server, vLLM, a LiteLLM proxy, or a hosted provider. When a hosted provider is used, question text and tool results (including municipal data) leave the server; municipalities that cannot allow this use the local option.

## Known limits

- The deterministic mode understands a fixed set of intents; unusual phrasing falls back to the current situation.
- An LLM can still word a correct number badly; the answer carries a disclaimer and the source list for verification.
- No conversation memory: each question is answered on its own.
