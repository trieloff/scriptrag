# ScriptRAG Architecture Documentation

## System Overview

ScriptRAG is a graph-based screenplay analysis system that combines traditional text
processing with modern AI embeddings to provide powerful search and visualization
capabilities for screenwriters and production teams.

## High-Level Architecture

```mermaid
graph TB
    subgraph "Client Layer"
        WEB[Web Applications]
        CLI[CLI Tools]
        SDK[SDKs/Libraries]
        THIRD[Third-party Tools]
    end

    subgraph "API Layer"
        REST[REST API<br/>FastAPI]
        AUTH[Auth Middleware<br/>Future]
        CORS[CORS Middleware]
    end

    subgraph "Business Logic"
        PARSER[Fountain Parser]
        EMBED[Embedding Generator]
        SEARCH[Search Engine]
        GRAPH[Graph Builder]
        DBOPS[DB Operations]
    end

    subgraph "Data Layer"
        PG[(PostgreSQL<br/>+ pgvector)]
        CACHE[(Redis Cache<br/>Future)]
    end

    subgraph "AI/ML Layer"
        LLM[LLM Service]
        VECTOR[Vector Embeddings]
    end

    WEB --> REST
    CLI --> REST
    SDK --> REST
    THIRD --> REST

    REST --> AUTH
    AUTH --> CORS
    CORS --> PARSER
    CORS --> EMBED
    CORS --> SEARCH
    CORS --> GRAPH

    PARSER --> DBOPS
    EMBED --> DBOPS
    SEARCH --> DBOPS
    GRAPH --> DBOPS

    DBOPS --> PG
    DBOPS --> CACHE

    EMBED --> LLM
    LLM --> VECTOR
    VECTOR --> PG
```

## Component Architecture

### 1. REST API Layer

The API layer provides a RESTful interface to all ScriptRAG functionality:

```mermaid
graph LR
    subgraph "FastAPI Application"
        APP[App Factory]
        ROUTES[Route Handlers]
        DEPS[Dependencies]
        MIDDLE[Middleware]
    end

    subgraph "Endpoints"
        SCRIPTS[/scripts]
        SCENES[/scenes]
        SEARCH[/search]
        EMBED[/embeddings]
        GRAPHS[/graphs]
    end

    APP --> ROUTES
    APP --> MIDDLE
    ROUTES --> DEPS
    ROUTES --> SCRIPTS
    ROUTES --> SCENES
    ROUTES --> SEARCH
    ROUTES --> EMBED
    ROUTES --> GRAPHS
```

**Key Components:**

- **FastAPI Framework**: Modern, async Python web framework
- **Pydantic Models**: Request/response validation and serialization
- **Dependency Injection**: Clean separation of concerns
- **OpenAPI Generation**: Automatic API documentation

### 2. Database Architecture

The database layer uses PostgreSQL with pgvector extension for hybrid search:

```mermaid
erDiagram
    SCRIPTS ||--o{ SCENES : contains
    SCRIPTS ||--o{ CHARACTERS : features
    SCENES ||--o{ SCENE_CHARACTERS : appears_in
    CHARACTERS ||--o{ SCENE_CHARACTERS : appears_in
    SCENES ||--|| EMBEDDINGS : has

    SCRIPTS {
        uuid id PK
        string title
        string author
        timestamp created_at
        timestamp updated_at
        json metadata
    }

    SCENES {
        uuid id PK
        uuid script_id FK
        int scene_number
        string heading
        text content
        float page_start
        float page_end
        json elements
    }

    CHARACTERS {
        uuid id PK
        uuid script_id FK
        string name
        int dialogue_count
        json metadata
    }

    EMBEDDINGS {
        uuid id PK
        uuid scene_id FK
        vector embedding
        string model_name
        timestamp created_at
    }

    SCENE_CHARACTERS {
        uuid scene_id FK
        uuid character_id FK
        int dialogue_count
    }
```

### 3. GraphRAG Integration

The GraphRAG pattern combines graph relationships with retrieval-augmented generation:

```mermaid
graph TB
    subgraph "Graph Construction"
        SCRIPT[Script Data]
        PARSER[Parse Relationships]
        GRAPH[Build Graph]
    end

    subgraph "Vector Search"
        QUERY[User Query]
        EMBED[Generate Embedding]
        SIMILAR[Find Similar]
    end

    subgraph "Graph Traversal"
        START[Start Nodes]
        TRAVERSE[Traverse Relations]
        EXPAND[Expand Context]
    end

    subgraph "RAG Pipeline"
        CONTEXT[Gather Context]
        PROMPT[Build Prompt]
        GENERATE[LLM Generation]
    end

    SCRIPT --> PARSER
    PARSER --> GRAPH

    QUERY --> EMBED
    EMBED --> SIMILAR

    SIMILAR --> START
    START --> TRAVERSE
    TRAVERSE --> EXPAND

    EXPAND --> CONTEXT
    CONTEXT --> PROMPT
    PROMPT --> GENERATE
```

### 4. Search Architecture

Multi-modal search combining text and semantic similarity:

```mermaid
flowchart LR
    subgraph "Search Request"
        QUERY[Query Text]
        FILTERS[Filters]
    end

    subgraph "Search Modes"
        TEXT[Text Search<br/>PostgreSQL FTS]
        VECTOR[Vector Search<br/>pgvector]
        HYBRID[Hybrid Search<br/>Reciprocal Rank Fusion]
    end

    subgraph "Post-Processing"
        RANK[Ranking]
        FILTER[Filtering]
        SNIPPET[Snippet Generation]
    end

    QUERY --> TEXT
    QUERY --> VECTOR
    TEXT --> HYBRID
    VECTOR --> HYBRID

    HYBRID --> RANK
    RANK --> FILTER
    FILTERS --> FILTER
    FILTER --> SNIPPET
```

**Search Types:**

1. **Text Search**: PostgreSQL full-text search with stemming and ranking
2. **Vector Search**: Cosine similarity using pgvector extension
3. **Hybrid Search**: Combines both methods using reciprocal rank fusion

### 5. Embedding Pipeline

Document processing and embedding generation flow:

```mermaid
sequenceDiagram
    participant Client
    participant API
    participant Parser
    participant Queue
    participant LLM
    participant DB

    Client->>API: Upload Script
    API->>Parser: Parse Fountain
    Parser->>DB: Store Scenes
    API->>Client: Script ID

    Client->>API: Generate Embeddings
    API->>Queue: Queue Scenes

    loop For Each Scene
        Queue->>LLM: Generate Embedding
        LLM->>Queue: Vector Response
        Queue->>DB: Store Embedding
    end

    API->>Client: Embedding Status
```

### 6. Graph Visualization Pipeline

Character and relationship graph generation:

```mermaid
flowchart TB
    subgraph "Data Collection"
        SCENES[Scene Data]
        CHARS[Character Data]
        DIALOG[Dialogue Analysis]
    end

    subgraph "Graph Building"
        NODES[Create Nodes]
        EDGES[Create Edges]
        WEIGHT[Calculate Weights]
    end

    subgraph "Graph Processing"
        FILTER[Apply Filters]
        LAYOUT[Graph Layout]
        SERIAL[Serialize]
    end

    SCENES --> NODES
    CHARS --> NODES
    DIALOG --> EDGES

    NODES --> WEIGHT
    EDGES --> WEIGHT

    WEIGHT --> FILTER
    FILTER --> LAYOUT
    LAYOUT --> SERIAL
```

## Data Flow Examples

### 1. Script Upload Flow

```mermaid
sequenceDiagram
    participant User
    participant API
    participant Parser
    participant DB
    participant Storage

    User->>API: POST /scripts/upload
    API->>Parser: Parse Fountain
    Parser->>Parser: Extract Scenes
    Parser->>Parser: Extract Characters
    Parser->>DB: Begin Transaction

    DB->>DB: Insert Script
    DB->>DB: Insert Scenes
    DB->>DB: Insert Characters
    DB->>DB: Create Relations

    DB->>API: Commit Transaction
    API->>User: Script Response
```

### 2. Semantic Search Flow

```mermaid
sequenceDiagram
    participant User
    participant API
    participant Embedder
    participant DB
    participant Ranker

    User->>API: POST /search/similar
    API->>Embedder: Generate Query Embedding
    Embedder->>API: Query Vector

    API->>DB: Vector Similarity Search
    DB->>DB: Calculate Distances
    DB->>API: Similar Scenes

    API->>Ranker: Rank Results
    Ranker->>API: Ranked Results
    API->>User: Search Response
```

### 3. Graph Generation Flow

```mermaid
flowchart LR
    subgraph "Request"
        REQ[Character Graph Request]
        PARAMS[Parameters:<br/>- Character Name<br/>- Depth<br/>- Min Interactions]
    end

    subgraph "Query Phase"
        Q1[Find Character Scenes]
        Q2[Find Co-occurring Characters]
        Q3[Calculate Interactions]
    end

    subgraph "Build Phase"
        B1[Create Character Nodes]
        B2[Create Relationship Edges]
        B3[Add Metadata]
    end

    subgraph "Response"
        RESP[Graph Data:<br/>- Nodes<br/>- Edges<br/>- Metadata]
    end

    REQ --> Q1
    PARAMS --> Q1
    Q1 --> Q2
    Q2 --> Q3
    Q3 --> B1
    B1 --> B2
    B2 --> B3
    B3 --> RESP
```

## Deployment Architecture

### Production Deployment

```mermaid
graph TB
    %% Native Process Architecture - No Containers

    LB[Nginx Load Balancer<br/>Native Process]

    %% ScriptRAG Processes (managed by systemd/supervisor)
    API1[uvx scriptrag serve<br/>Process 1 - Port 8001]
    API2[uvx scriptrag serve<br/>Process 2 - Port 8002]
    API3[uvx scriptrag serve<br/>Process 3 - Port 8003]

    %% Database (native PostgreSQL installation)
    PRIMARY[(PostgreSQL Primary<br/>Native Process)]
    REPLICA1[(PostgreSQL Replica 1<br/>Native Process)]
    REPLICA2[(PostgreSQL Replica 2<br/>Native Process)]

    %% Cache (native Redis installation)
    REDIS[(Redis<br/>Native Process)]

    %% LLM Services (external APIs or local processes)
    LLM1[LLM API Endpoint 1]
    LLM2[LLM API Endpoint 2]

    LB --> API1
    LB --> API2
    LB --> API3

    API1 --> PRIMARY
    API2 --> REPLICA1
    API3 --> REPLICA2

    API1 --> REDIS
    API2 --> REDIS
    API3 --> REDIS

    API1 --> LLM1
    API2 --> LLM2
    API3 --> LLM1

    %% Annotations
    LB -.- NOTE1[All services run as<br/>native OS processes]
    API3 -.- NOTE2[Managed by systemd<br/>or supervisor]
    REDIS -.- NOTE3[No containerization<br/>overhead]

    style NOTE1 fill:#f9f9f9,stroke:#333,stroke-dasharray: 5 5
    style NOTE2 fill:#f9f9f9,stroke:#333,stroke-dasharray: 5 5
    style NOTE3 fill:#f9f9f9,stroke:#333,stroke-dasharray: 5 5
```

### Modern Deployment Architecture

ScriptRAG leverages modern Python tooling for simple, efficient deployment:

```bash
# Production deployment with uv
uv pip install scriptrag

# Run with environment configuration
SCRIPTRAG_DATABASE_URL=postgresql://... \
SCRIPTRAG_REDIS_URL=redis://localhost:6379 \
SCRIPTRAG_LLM_ENDPOINT=http://llm-service:8080 \
uvx scriptrag serve

# Scale horizontally with process managers
# Using systemd, supervisor, or similar tools
# No containers needed - just Python processes
```

#### Service Dependencies

- **PostgreSQL**: Install via system package manager or use managed service
- **Redis**: Optional caching layer, install via package manager
- **Nginx**: Reverse proxy for load balancing (if needed)

All services run as native processes, no containerization overhead.

## Security Architecture

### API Security Layers

```mermaid
graph TB
    subgraph "External"
        CLIENT[Client Request]
    end

    subgraph "Edge Security"
        WAF[Web Application Firewall]
        DDOS[DDoS Protection]
    end

    subgraph "Transport Security"
        TLS[TLS/SSL]
        CERT[Certificate Management]
    end

    subgraph "Application Security"
        AUTH[Authentication<br/>Future: JWT]
        AUTHZ[Authorization<br/>Future: RBAC]
        RATE[Rate Limiting]
        VALID[Input Validation]
    end

    subgraph "Data Security"
        ENCRYPT[Encryption at Rest]
        AUDIT[Audit Logging]
    end

    CLIENT --> WAF
    WAF --> DDOS
    DDOS --> TLS
    TLS --> AUTH
    AUTH --> AUTHZ
    AUTHZ --> RATE
    RATE --> VALID
    VALID --> ENCRYPT
```

## Performance Considerations

### Caching Strategy

```mermaid
graph LR
    subgraph "Cache Layers"
        L1[Application Cache<br/>In-Memory]
        L2[Redis Cache<br/>Distributed]
        L3[Database Cache<br/>Query Results]
    end

    subgraph "Cache Keys"
        K1[script:{id}]
        K2[scenes:{script_id}]
        K3[search:{query_hash}]
        K4[graph:{params_hash}]
    end

    subgraph "TTL Strategy"
        T1[Scripts: 1 hour]
        T2[Searches: 15 min]
        T3[Graphs: 30 min]
    end

    K1 --> L1
    K2 --> L2
    K3 --> L2
    K4 --> L3

    L1 --> T1
    L2 --> T2
    L3 --> T3
```

### Optimization Points

1. **Database Optimization**
   - Proper indexing on search columns
   - Partitioning for large script collections
   - Connection pooling
   - Query optimization

2. **API Optimization**
   - Async request handling
   - Response compression
   - Pagination for large results
   - Field selection (GraphQL-like)

3. **Embedding Optimization**
   - Batch processing
   - Model caching
   - Quantization for storage
   - Incremental updates

## Monitoring and Observability

### Metrics Collection

```mermaid
graph TB
    subgraph "Application Metrics"
        APP[API Metrics<br/>- Request Rate<br/>- Response Time<br/>- Error Rate]
    end

    subgraph "Infrastructure Metrics"
        INFRA[System Metrics<br/>- CPU Usage<br/>- Memory<br/>- Disk I/O]
    end

    subgraph "Business Metrics"
        BIZ[Usage Metrics<br/>- Scripts Uploaded<br/>- Searches/Day<br/>- Active Users]
    end

    subgraph "Monitoring Stack"
        PROM[Prometheus]
        GRAF[Grafana]
        ALERT[AlertManager]
    end

    APP --> PROM
    INFRA --> PROM
    BIZ --> PROM

    PROM --> GRAF
    PROM --> ALERT
```

## Future Architecture Enhancements

### Planned Improvements

1. **Microservices Architecture**
   - Separate embedding service
   - Independent search service
   - Graph computation service

2. **Event-Driven Architecture**
   - Message queue for async processing
   - Event sourcing for script changes
   - WebSocket support for real-time updates

3. **Multi-Tenant Support**
   - User authentication/authorization
   - Data isolation
   - Usage quotas

4. **Advanced AI Integration**
   - Multiple LLM providers
   - Custom fine-tuned models
   - Script generation capabilities

## Technology Stack

### Current Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| API Framework | FastAPI | REST API server |
| Database | PostgreSQL + pgvector | Data storage and vector search |
| Language | Python 3.12 | Primary development language |
| Parser | Custom Fountain Parser | Script parsing |
| Embeddings | OpenAI/Local Models | Semantic search |
| Deployment | uv/uvx | Modern Python packaging |
| Documentation | OpenAPI/Swagger | API documentation |

### Infrastructure Requirements

**Minimum Requirements:**

- 2 CPU cores
- 4GB RAM
- 20GB storage
- PostgreSQL 15+ with pgvector

**Recommended Production:**

- 8+ CPU cores
- 16GB+ RAM
- 100GB+ SSD storage
- Load balancer
- Redis cache
- Monitoring stack

## Integration Points

### External Services

1. **LLM Providers**
   - OpenAI API
   - Local models (Ollama)
   - Custom models

2. **Storage Services**
   - S3-compatible object storage
   - CDN for static assets

3. **Analytics Services**
   - Usage tracking
   - Performance monitoring
   - Error tracking

### Client Integration

1. **REST API Clients**
   - Direct HTTP calls
   - Generated SDKs
   - GraphQL gateway (future)

2. **Export Formats**
   - Final Draft XML
   - PDF generation
   - Other screenplay formats

## Conclusion

ScriptRAG's architecture is designed to be scalable, maintainable, and extensible.
The combination of traditional database operations with modern AI capabilities provides
a powerful platform for screenplay analysis and management. The modular design allows
for easy enhancement and integration with other tools in the screenwriting ecosystem.
