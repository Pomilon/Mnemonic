# Mnemonic: Semantic Meta-Search & Synthesis Engine

Mnemonic is a high-performance semantic search middleware that transforms raw web data into a vectorized knowledge stream. It leverages local AI to understand intent, recalibrate results based on feedback, and synthesize findings into actionable intelligence.

## Key Features

- **Semantic Memory**: Uses **LanceDB** and **Sentence-Transformers** (`all-MiniLM-L6-v2`) to store and retrieve search results based on 384-dimensional query embeddings.
- **Dynamic Landing UX**: A cinematic transition from a minimalist Google-style landing to a dense, multi-panel search workstation.
- **Synthesis Workspace**: Pin search results to a side canvas and use a **local LLM (via Ollama)** to generate summarized insights and drafts.
- **Bento Box UI**: A gapless, length-driven grid system that scales card sizes based on content volume, built with **Tailwind CSS** and **HTMX**.
- **Vector Recalibration**: A self-correcting feedback loop. Rejecting a result applies a negative penalty to the query vector, shifting the search focus away from irrelevant clusters.
- **Live Telemetry**: A terminal-style console providing real-time system logs and engine metrics via **Server-Sent Events (SSE)**.
- **Admin Dashboard**: Secure management portal (`/admin`) to monitor cache performance, view stored queries, and perform factory resets.

## Architecture

1.  **Aggregator**: Parallel multi-engine fetching (currently via DuckDuckGo, extensible to Google/Bing).
2.  **Refinement**: URL normalization, de-duplication, and semantic re-ranking using **BM25 + Cosine Similarity**.
3.  **Memory**: Vector database with configurable TTL, distance thresholds, and rejection-based conflict resolution.
4.  **Synthesis**: Local LLM integration (Llama 3/Mistral) for zero-latency context summarization.

## Getting Started

### Prerequisites
- Python 3.10+
- [Ollama](https://ollama.com/) (Optional, for synthesis features)
- `pip install -r requirements.txt`

### Configuration
Mnemonic is highly configurable. You can use either a `.env` file or a `config.json` file in the root directory.

```bash
cp .env.example .env
# OR
cp config.json.example config.json
```

**Key Configs:**
- `MNEMONIC_ADMIN_TOKEN`: Secure token for the admin dashboard.
- `OLLAMA_MODEL`: The model name to use for synthesis (e.g., `llama3`).
- `MAX_RESULTS_PER_ENGINE`: Number of nodes to pull per search pass.
- `CACHE_TTL_DAYS`: How long results remain in semantic memory.

### Running with Docker (Recommended)
Mnemonic is fully containerized. To build and start the environment:

```bash
docker compose up -d
```
Visit `http://localhost:8000` to start querying.

**Note on Ollama & Docker**: If you are running Ollama on your host machine, the default `OLLAMA_BASE_URL` in `docker-compose.yml` is set to `http://host.docker.internal:11434`. This ensures the container can reach your local AI models for synthesis.

### Running Manually
```bash
# Start the FastAPI server
export PYTHONPATH=$PYTHONPATH:.
python3 src/mnemonic/api/main.py
```
Visit `http://localhost:8000` to start searching.

## Security
- **Admin Access**: Protected by token-based `HttpOnly` cookie authentication.
- **Privacy First**: Mnemonic acts as a pass-through processor; no external AI APIs are used. All synthesis happens locally on your hardware.

## License
MIT License - See [LICENSE](LICENSE) for details.
