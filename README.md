# Mnemonic: Semantic Meta-Search & Synthesis Engine

Mnemonic is a semantic search middleware that transforms raw web data into a vectorized knowledge stream. It leverages local AI to understand intent, recalibrate results based on feedback, and synthesize findings into actionable intelligence.

## Showcase

<p align="center">
  <img src="assets/home.png" alt="Mnemonic Landing" width="800">
  <br>
  <em>Minimalist landing page.</em>
</p>

<p align="center">
  <img src="assets/search.png" alt="Mnemonic Search Interface" width="800">
  <br>
  <em>Dense, multi-panel search workstation with Synthesis Workspace.</em>
</p>

## Key Features

- **Semantic Memory**: Uses **LanceDB** and **Sentence-Transformers** to store and retrieve search results based on high-dimensional query embeddings.
- **HyDE Intent Expansion**: Implements **Hypothetical Document Embeddings** to expand short queries into dense semantic vectors, significantly improving retrieval accuracy.
- **Multi-Engine Aggregator**: Parallel fetching across **Brave, Google, Bing, DuckDuckGo, Wikipedia, HackerNews, StackOverflow, and ArXiv**.
- **Synthesis Workspace**: Pin search results to a side canvas and use a **local LLM (via Ollama or Llama.cpp)** to generate summarized insights and drafts.
- **Vector Recalibration**: A self-correcting feedback loop. Rejecting a result applies a negative penalty to the query vector, shifting the search focus away from irrelevant clusters.
- **Real-time Verbose Feedback**: A dedicated search status bar and collapsible terminal provide live telemetry on expansion, retrieval, and re-ranking phases.
- **Admin Dashboard**: Secure management portal (`/admin`) for runtime configuration of search parameters, synthesis models, and embedding catalog.

## Architecture

1.  **Aggregator**: Distributed query pipeline that normalizes results from multiple web and academic providers.
2.  **Search System**: Orchestrates the retrieval lifecycle, including HyDE expansion, semantic filtering, and cross-engine deduplication.
3.  **Refinement**: Dynamic re-ranking using **BM25 + Semantic Similarity** and privacy-focused URL cleaning.
4.  **Memory**: Persistent vector store with configurable TTL, distance thresholds, and rejection-based penalty marking.
5.  **Synthesis**: Local-first LLM integration supporting both Ollama (API) and Llama.cpp (Direct) providers.

## Getting Started

### Prerequisites
- Python 3.10+
- [Ollama](https://ollama.com/) or [Llama.cpp](https://github.com/ggerganov/llama.cpp)
- `pip install -r requirements.txt`

### Configuration
Mnemonic uses a dual-configuration system for maximum security and ease of use:

1.  **System Config (`.env`)**: Sensitive secrets and API keys.
    ```bash
    cp .env.example .env
    ```
2.  **App Config (`src/mnemonic/aggregator/*.json`)**: Operational settings.
    *   **Auto-Initialization**: Missing JSON configs are automatically generated from `.example` templates on first run.
    *   **Private Isolation**: Local configuration files are automatically ignored by Git to protect your custom environment.
    *   **Live Updates**: Most settings (Search limits, HyDE toggle, LLM providers) can be updated live via the **Admin Dashboard**.

**Key Environment Variables:**
- `MNEMONIC_ADMIN_TOKEN`: Secure token for accessing the admin dashboard.
- `BRAVE_API_KEY`, `GOOGLE_API_KEY`, etc.: API keys for optional search providers.

### Running with Docker (Recommended)
Mnemonic is fully containerized. To build and start the environment:

```bash
docker compose up -d
```
Visit `http://localhost:8000` to start querying.

### Running Manually
```bash
# Start the FastAPI server
export PYTHONPATH=$PYTHONPATH:.
python3 src/mnemonic/api/main.py
```

## Security & Privacy
- **Local First**: All embedding and synthesis operations happen on your hardware. No search data or context is sent to third-party AI providers.
- **Admin Security**: The dashboard is protected by token-based authentication with secure `HttpOnly` cookies.
- **Zero-Trust Config**: Sensitive keys never touch the application-level JSON files and remain strictly in the `.env` layer.

## Roadmap

- **Export to Markdown**: One-click download of synthesized findings and pinned references.
- **Advanced Filtering**: UI controls to filter results by domain, date, or content category.
- **Custom Synthesis Styles**: Choice between Deep Research, Quick Summary, or Bullet Point modes.
- **Graph Visualization**: Visual mapping of semantic relationships between cached search nodes.
- **Mobile Optimization**: PWA support and responsive refinements for the search workstation.

## License
MIT License - See [LICENSE](LICENSE) for details.
