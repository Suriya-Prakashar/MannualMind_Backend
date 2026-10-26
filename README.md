# ManualMind — Technical Manual Assistant Backend

ManualMind is an enterprise-grade technical manual assistant built with **FastAPI**, **MongoDB Atlas**, **Google Gemini GenAI**, and advanced **Multimodal RAG**. It understands technical queries, performs hybrid vector & keyword retrieval, extracts and serves PDF schematic diagrams, retains multi-turn session history, and supports token-by-token streaming with resilience protection.

---

## 🏗️ Architecture & Project Structure

The project follows a modular, clean-architecture pattern separating routing, models, services, repositories, and utilities:

```text
ManualMind-backend/
├── app/
│   ├── __init__.py
│   ├── config.py                       # Global settings and environment configuration
│   ├── database.py                     # MongoDB Atlas connection manager & lifecycles
│   ├── main.py                         # FastAPI application entrypoint & static mount
│   │
│   ├── api/                            # REST & Streaming API Endpoints
│   │   ├── __init__.py
│   │   ├── documents.py                # Document upload, ingestion & status endpoints
│   │   └── query.py                    # Query execution & SSE streaming endpoints
│   │
│   ├── models/                         # Domain Pydantic Schemas & Data Contracts
│   │   ├── __init__.py
│   │   ├── routing.py                  # RouteType, QueryIntent, StructuredRoutingDecision
│   │   └── session.py                  # SessionContext, ChatTurn, ApprovalState
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── core/                       # Core Business & AI Engines
│   │   │   ├── __init__.py
│   │   │   ├── answer_generation_service.py # Gemini RAG answer gen, streaming & retry
│   │   │   ├── chunk_embedding_service.py   # Batch vector embedding for chunks
│   │   │   ├── chunk_service.py             # Recursive token-aware document chunking
│   │   │   ├── email_service.py             # SMTP email dispatch & validation
│   │   │   ├── embedding_service.py         # Google Gemini embedding client
│   │   │   ├── hybrid_search_service.py     # Hybrid search orchestrator
│   │   │   ├── image_resolver_service.py    # PDF diagram resolution & static URL builder
│   │   │   ├── ingestion_service.py         # End-to-end PDF processing pipeline
│   │   │   ├── maintenance_email_service.py # Equipment incident email composer
│   │   │   ├── pdf_service.py               # PyMuPDF text & image extraction
│   │   │   ├── query_router_service.py      # Intelligent intent classification & routing
│   │   │   ├── query_service.py             # Unified query execution orchestrator
│   │   │   ├── reranking_service.py         # Reciprocal Rank Fusion (RRF) reranker
│   │   │   ├── retrieval_service.py         # Multi-tier vector + fallback retrieval
│   │   │   ├── session_service.py           # Thread-safe multi-turn session tracker
│   │   │   ├── startup_processor.py         # Automatic startup indexing of manuals
│   │   │   ├── tool_registry.py             # External tool catalog & validation
│   │   │   └── vector_search_service.py     # Atlas vector search & keyword queries
│   │   │
│   │   ├── repositories/               # Data Access Layer
│   │   │   ├── __init__.py
│   │   │   ├── chunk_repository.py          # MongoDB chunk persistence & indexing
│   │   │   └── document_repository.py       # MongoDB document metadata tracking
│   │   │
│   │   └── utils/                      # Helper Utilities
│   │       ├── __init__.py
│   │       ├── database_indexes.py          # Atlas search & unique index definitions
│   │       └── file_hash.py                 # SHA-256 deduplication hashing
│   │
│   └── tests/                          # Consolidated Domain Test Suites (77 Tests)
│       ├── __init__.py
│       ├── test_suite_api.py           # Sync & SSE streaming API endpoint tests
│       ├── test_suite_ingestion.py     # PDF extraction, chunking, hashing & DB repositories
│       ├── test_suite_retrieval.py     # Hybrid search, embeddings, RRF, reranking & fallback
│       ├── test_suite_router.py        # Query understanding, tool registry & routing
│       └── test_suite_rag_and_tools.py # RAG, multimodal figures, 5-turn session memory & email tools

│
├── data/
│   ├── manuals/                        # Source PDF user & repair manuals
│   └── extracted/                      # Extracted images & page text
│
├── scripts/                            # Operational & Verification Scripts
│   ├── check_atlas_index.py
│   ├── check_embeddings.py
│   ├── check_manuals.py
│   ├── verify_maintenance_email.py
│   ├── verify_query_understanding.py
│   ├── verify_rag_query.py
│   ├── verify_real_pdf_embedding.py
│   ├── verify_real_pdf_ingestion.py
│   └── verify_vector_search.py
│
├── .env.example                        # Template for environment variables
├── requirements.txt                    # Project dependencies
└── README.md                           # Documentation
```

---

## 🚀 Key Features

### 1. Multimodal RAG with PDF Diagram Retrieval
- During PDF ingestion, PyMuPDF extracts both high-resolution diagrams and page text.
- Retrieved chunks associate page numbers with their extracted figures.
- Static assets are mounted at `/static/images/...` and served directly.
- The AI includes Markdown image links in the answer, and returns structured `images` metadata:
  ```json
  "images": [
    {
      "url": "/static/images/<file_hash>/images/page_38_image_1.jpeg",
      "page_number": 38,
      "caption": "Figure on Page 38 (<file_hash>)"
    }
  ]
  ```

### 2. Multi-Turn Session Memory (Last 5 Turns)
- In-memory thread-safe `SessionService` tracks recent user queries and answers.
- The last 5 conversation turns are formatted and injected into Gemini prompts to resolve pronouns (e.g. *"how do I replace it?"* after discussing the motherboard) and maintain continuity.

### 3. Resilience, Streaming & Retry Protection
- **SSE Word Streaming:** `POST /query/stream` yields Server-Sent Events (`metadata`, `token`, `done`) for instant perceived latency.
- **Retrieval Fallback:** If vector search yields 0 candidates due to phrasing mismatch, a multi-tier keyword and relaxed term retrieval fallback recovers relevant context.
- **3x Retry with 3s Interval:** Transient AI failures (rate limits, timeouts) automatically retry up to 3 times before graceful degradation.

### 4. Intelligent Query Understanding & Routing
- Classifies user intent into `DIRECT`, `RAG`, `TOOL`, or `CLARIFY`.
- Handles general chitchat and greetings directly without wasting RAG tokens.
- Supports multi-step actions (e.g., draft incident email, verify inventory, check ticketing).

---

## 🛠️ Setup & Installation

### 1. Prerequisites
- Python 3.10+ (Tested on Python 3.14)
- MongoDB Atlas cluster with Vector Search index enabled
- Google Gemini API Key

### 2. Environment Configuration
Copy `.env.example` to `.env` and fill in your credentials:
```bash
cp .env.example .env
```

### 3. Install Dependencies
```bash
python -m venv venv
# Windows:
.\venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
```

---

## ⚡ Running the Server

Start the FastAPI application with Uvicorn:
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
- **Interactive OpenAPI Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health Check:** [http://localhost:8000/health](http://localhost:8000/health)

---

## 📡 API Endpoints

### 1. Standard Query (`POST /query/`)
**Request:**
```json
{
  "query": "Explain step by step procedure to replace the motherboard",
  "session_id": "session-123"
}
```

**Response:**
```json
{
  "route": "RAG",
  "answer": "Here is the step-by-step procedure...",
  "sources": [
    {
      "page_number": 38,
      "chunk_id": "...",
      "snippet": "Main PBA Disassembly..."
    }
  ],
  "images": [
    {
      "url": "/static/images/.../images/page_38_image_1.jpeg",
      "page_number": 38,
      "caption": "Figure on Page 38 (...)"
    }
  ],
  "session_id": "session-123"
}
```

### 2. Streaming Query (`POST /query/stream`)
**Request:**
```bash
curl -N -X POST "http://localhost:8000/query/stream" \
  -H "Content-Type: application/json" \
  -d '{"query": "How do I remove the rear case?", "session_id": "session-123"}'
```

**Events Streamed:**
```text
event: metadata
data: {"route": "RAG", "sources": [...], "images": [...]}

event: token
data: {"token": "To"}

event: token
data: {"token": " remove"}

event: done
data: {"status": "completed"}
```

---

## 🧪 Testing

Run the consolidated automated test suites (77 tests across 5 clean domain files):
```bash
pytest -q
```
All tests mock external API and SMTP calls, ensuring quick (<6s) and isolated test execution.

