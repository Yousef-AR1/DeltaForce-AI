# DeltaForce AI

DeltaForce AI is a local, domain-specialized assistant for **Delta Force** and related esports information.

The project combines a local language model with retrieval-augmented generation (RAG), multilingual semantic search, structured catalogs, source metadata, freshness-aware ranking, and deterministic direct answers for complete lists and fixed facts.

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
- Delta Force weapons, operators, maps, modes, vehicles, bosses, ammo, systems, releases and regional versions
- Garena MENA / EMEA esports data and a structured Garena MENA Discord tournament archive
- Automated tests and evaluation questions

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

- Python
- Streamlit
- Qwen3-4B-Instruct-2507
- LM Studio
- RAG
- Sentence-Transformers
- `paraphrase-multilingual-MiniLM-L12-v2`
- FAISS
- JSON
- Pytest

## Project Structure

```text
DeltaForce-AI/
├── app.py
├── config.py
├── requirements.txt
├── .env.example
├── .gitignore
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

## Setup

### 1. Requirements

Recommended environment:

- Windows 10/11
- Python 3.11
- LM Studio
- Qwen3-4B-Instruct-2507 loaded in LM Studio

### 2. Create the virtual environment

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

### 3. Start LM Studio

1. Open LM Studio.
2. Load **Qwen3-4B-Instruct-2507**.
3. Start the local API server.
4. Keep the default API address:

```text
http://localhost:1234/v1
```

### 4. Build the FAISS index

Run:

```bat
build_index.bat
```

or:

```bat
python -m ingestion.indexer
```

The generated files are:

```text
vector_db/index.faiss
vector_db/metadata.json
```

They are ignored by Git because they can be regenerated from the included knowledge data.

### 5. Run the application

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

The retriever considers semantic relevance together with lexical relevance, source trust, freshness, knowledge type, intent and topic.

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

## Testing

Run:

```bat
pytest
```

## Evaluation

With LM Studio running and the FAISS index built:

```bat
python -m evaluation.evaluate
```

Generated evaluation files are written to:

```text
evaluation/results/
```

## Repository Notes

- `.env` is ignored by Git.
- Virtual environments and Python cache files are ignored.
- Local model files are ignored.
- Generated FAISS files are ignored and can be rebuilt.
- `.env.example` contains only local development defaults.

## Model

The application uses only:

```text
Qwen3-4B-Instruct-2507
```

There is no model selector or custom model input in the final application.
