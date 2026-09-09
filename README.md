# DeltaForce AI

DeltaForce AI is a local, domain-specialized assistant for **Delta Force** and related esports information.

The project combines a local language model with retrieval-augmented generation (RAG), multilingual semantic search, structured catalogs, source metadata, freshness-aware ranking, deterministic direct answers, and Docker support for consistent application deployment.

## Main Features

- Local inference through **LM Studio**
- Fixed model: **Qwen3-4B-Instruct-2507**
- **Streamlit** chat interface
- Arabic and English support
- Arabic dialect-aware semantic intent routing
- Multilingual Sentence-Transformers embeddings
- **FAISS** vector search
- Source trust and freshness-aware re-ranking
- Safe abstention when evidence is not reliable enough
- Structured catalogs for complete lists and fixed facts
- Delta Force weapons, operators, maps, modes, vehicles, bosses, ammo, systems, releases, and regional versions
- Garena MENA / EMEA esports data
- Structured Garena MENA Discord tournament archive
- Automated tests and evaluation questions
- **Docker / Docker Compose support**

## Architecture

```text
User Question
    |
Streamlit
    |
ChatService
    |
Semantic Intent Router
    |
    +----------------------------+
    |                            |
Structured Direct Route         RAG Route
    |                            |
Catalog Services                Query Analyzer
    |                            |
Direct Answer                   Multilingual Embedding
                                 |
                                 FAISS Retrieval
                                 |
                                 Re-ranking
                                 |
                                 Context Validation
                                 |
                                 Prompt Builder
                                 |
                                 LM Studio / Qwen
                                 |
                                 Grounded Answer + Sources
```

## Docker Architecture

The application is containerized with Docker, while the Qwen model continues to run locally through LM Studio on the host machine.

```text
Windows Host
|
|-- LM Studio
|   `-- Qwen3-4B-Instruct-2507
|       `-- Local API: port 1234
|
`-- Docker Desktop
    `-- deltaforce-ai container
        |-- Python 3.11
        |-- Streamlit
        |-- RAG
        |-- FAISS
        |-- Sentence-Transformers
        `-- Application code
```

The Docker container connects to LM Studio through:

```text
http://host.docker.internal:1234/v1
```

The local Qwen model is not copied into the Docker image.

## Why Two Answer Paths?

RAG is useful for descriptive and evidence-based questions, but a Top-K retrieval step does not guarantee that every item in a long list will be returned.

For questions that require a complete or fixed answer, the project uses structured catalogs directly.

Examples:

- `اعطيني جميع أسلحة الرشاش الخفيف`
- `اعطيني جميع الشخصيات الحالية`
- `شو الموسم الحالي؟`
- `متى نزلت اللعبة على الموبايل؟`
- `What are the Global, Garena, and China versions?`

Descriptive questions continue through the RAG pipeline.

## Technology Stack

- Python 3.11
- Streamlit
- Qwen3-4B-Instruct-2507
- LM Studio
- RAG
- Sentence-Transformers
- `paraphrase-multilingual-MiniLM-L12-v2`
- FAISS
- JSON
- Pytest
- Docker
- Docker Compose
- WSL 2 on Windows

## Project Structure

```text
DeltaForce-AI/
├── app.py
├── config.py
├── requirements.txt
├── .env.example
├── .gitignore
├── .dockerignore
├── Dockerfile
├── docker-compose.yml
├── docker-start.bat
├── docker-stop.bat
├── run_app.bat
├── build_index.bat
├── setup_windows.bat
├── services/
├── rag/
├── llm/
├── ingestion/
├── data/
├── vector_db/
├── evaluation/
├── tests/
└── utils/
```

# Running the Project with Docker

## 1. Requirements

Install:

- Windows 10/11
- Docker Desktop
- WSL 2
- LM Studio
- Qwen3-4B-Instruct-2507

Docker Desktop should use the WSL 2 backend.

To verify Docker:

```powershell
docker --version
docker compose version
```

To verify WSL:

```powershell
wsl --status
```

## 2. Start LM Studio

1. Open LM Studio.
2. Open **Developer → Local Server**.
3. Load:

```text
Qwen3-4B-Instruct-2507
```

4. Start the local server on port:

```text
1234
```

5. Enable **Serve on Local Network** if required by the installed LM Studio version.

LM Studio should remain running while the application is using the local model.

## 3. Build and Start the Docker Container

The easiest method on Windows is:

```bat
docker-start.bat
```

This runs:

```powershell
docker compose up --build
```

During the first build Docker will:

1. Download the Python 3.11 base image.
2. Install the packages from `requirements.txt`.
3. Copy the application into the image.
4. Build the FAISS index.
5. Start the Streamlit application.

The initial build can take longer because Python packages and the embedding model may need to be downloaded.

## 4. Open the Application

After the container starts, open:

```text
http://localhost:8501
```

The Streamlit application is exposed from container port `8501` to the same port on the host machine.

## 5. Stop the Application

Use:

```bat
docker-stop.bat
```

or:

```powershell
docker compose down
```

## Docker Commands

### Build the image

```powershell
docker compose build
```

### Build and run

```powershell
docker compose up --build
```

### Run in the background

```powershell
docker compose up -d
```

### Stop containers

```powershell
docker compose down
```

### Show running containers

```powershell
docker ps
```

### Show application logs

```powershell
docker compose logs -f
```

### Rebuild after code or dependency changes

```powershell
docker compose up --build
```

## Docker to LM Studio Connection

Inside a Docker container, `localhost` refers to the container itself, not the Windows host.

For this reason, `docker-compose.yml` configures:

```yaml
environment:
  LMSTUDIO_BASE_URL: "http://host.docker.internal:1234/v1"
  LMSTUDIO_API_KEY: "lm-studio"
```

This allows the application inside Docker to communicate with LM Studio running on Windows.

The project reads the API address from the `LMSTUDIO_BASE_URL` environment variable.

## GPU Usage

The application container runs Streamlit, RAG, FAISS, and the Python application.

The Qwen model itself runs in **LM Studio on the Windows host**. GPU acceleration for Qwen is therefore controlled by LM Studio, not by the Docker container.

The current FAISS package is:

```text
faiss-cpu
```

This is sufficient for the current project data size.

## Dockerfile

The project uses `python:3.11-slim-bookworm` as the base image.

The Dockerfile:

- configures Python runtime settings
- installs required Linux packages
- installs `requirements.txt`
- copies the application
- builds the FAISS index
- exposes Streamlit on port `8501`
- includes a Streamlit health check
- starts the application automatically

## docker-compose.yml

Docker Compose defines the `deltaforce-ai` service and configures:

- application build
- container name
- port mapping
- LM Studio host connection
- host networking entry
- automatic restart policy

## Local Setup Without Docker

The project can also run directly on Windows.

### 1. Create the environment

Run:

```bat
setup_windows.bat
```

Or manually:

```bat
py -3.11 -m venv venv
venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
copy .env.example .env
```

### 2. Start LM Studio

Load:

```text
Qwen3-4B-Instruct-2507
```

and start the API server at:

```text
http://localhost:1234/v1
```

### 3. Build the FAISS index

```bat
build_index.bat
```

or:

```bat
python -m ingestion.indexer
```

### 4. Run Streamlit

```bat
run_app.bat
```

or:

```bat
streamlit run app.py
```

## Knowledge Design

### Knowledge Records

`data/knowledge.json` contains the RAG knowledge records.

Records can include:

- title
- content
- category
- knowledge type
- source name
- source URL
- source date
- season / patch
- language
- trust level
- current / historical state
- tags

### Structured Catalogs

Structured JSON catalogs are used for exhaustive or fixed facts such as:

- complete weapon lists
- operator roster
- maps
- modes
- vehicles
- bosses
- ammunition
- game systems
- release dates
- Global / Garena / China service information
- current season snapshot

This prevents complete-list questions from being limited by RAG Top-K retrieval.

## Dialect-Aware Routing

`services/semantic_intent_router.py` uses:

1. Arabic text normalization
2. Flexible high-confidence rules
3. Multilingual semantic embedding similarity
4. Fuzzy text matching fallback

Examples that can map to the same intent:

```text
اي سيزن اللعبه الان؟
شو السيزن هسا؟
وش السيزن الحين؟
احنا في سيزون كام دلوقتي؟
شنو السيزن هسه؟
فاش موسم حنا دابا؟
what season are we on rn?
```

## Source and Freshness Controls

Knowledge is separated into types such as:

- `official_fact`
- `historical`
- `recommendation`
- `community`
- `system_policy`

The retriever considers semantic relevance together with lexical relevance, source trust, freshness, knowledge type, intent, and topic.

For factual questions, weak or unsupported evidence can trigger safe abstention instead of an invented answer.

## Data Ingestion

Additional `.txt`, `.md`, `.pdf`, and `.docx` files can be added under:

```text
data/documents/official/
data/documents/historical/
data/documents/esports/
data/documents/community/
```

Rebuild the FAISS index after changing the RAG knowledge data.

When Docker is used, rebuilding the Docker image also rebuilds the index because the Dockerfile runs:

```text
python -m ingestion.indexer
```

## Testing

Run locally:

```bat
pytest
```

Or inside the running Docker container:

```powershell
docker exec -it deltaforce-ai pytest
```

## Evaluation

With LM Studio running and the FAISS index available:

```bat
python -m evaluation.evaluate
```

Inside Docker:

```powershell
docker exec -it deltaforce-ai python -m evaluation.evaluate
```

Generated evaluation files are written to:

```text
evaluation/results/
```

## Repository Notes

- `.env` is ignored by Git.
- `venv/` and `.venv/` are ignored.
- Python cache files are ignored.
- Local model files are ignored.
- Generated evaluation outputs are ignored.
- `.dockerignore` prevents local development files from being copied into the Docker image.
- The Qwen model is not included in the repository or Docker image.
- `.env.example` contains only local development defaults.

## Model

The application uses only:

```text
Qwen3-4B-Instruct-2507
```

There is no model selector or custom model input in the final application.

## Default Ports

| Service | Port |
|---|---:|
| Streamlit | `8501` |
| LM Studio API | `1234` |

## Quick Start

1. Start Docker Desktop.
2. Start LM Studio.
3. Load `Qwen3-4B-Instruct-2507`.
4. Start the LM Studio Local Server.
5. Run:

```bat
docker-start.bat
```

6. Open:

```text
http://localhost:8501
```

7. Stop the application with:

```bat
docker-stop.bat
```
