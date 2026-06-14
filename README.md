# ⚡ TALON 
**Splunk Agentic Ops Tool**

TALON is an autonomous data ingestion control plane. It uses Splunk Hosted Models, the Splunk MCP Server, and an Agentic TDD loop to automatically generate, test, and package `props.conf` parsing configurations for messy custom logs.

## 🏗️ Architecture

```mermaid
flowchart TB
    subgraph "TALON Control Plane (Streamlit)"
        UI[The Forge UI]
        State[TDD State Machine]
    end

    subgraph "AI Intelligence Layer"
        Agent[SchemaOps Agent<br>gpt-oss-120b]
        RAG[(CIM Oracle<br>ChromaDB Vector Store)]
    end

    subgraph "Splunk Ephemeral Sandbox"
        REST[REST API<br>Config Push & Ingest]
        MCP[Splunk MCP Server<br>JSON-RPC Tooling]
    end

    subgraph "Production Environment"
        SplunkProd[Live Splunk Enterprise]
    end

    %% Flow
    UI -- "1. Raw Log & Target Fields" --> State
    State -- "2. Prompt & Error Feedback" --> Agent
    Agent -- "3. Splunk JSON Config" --> State
    
    State -- "4. Push Config & Log via HTTP" --> REST
    State -- "5. Poll Validation Query via RPC" --> MCP
    MCP -- "6. Returns Extracted Fields" --> State
    
    State -- "7. Pass verified fields" --> RAG
    RAG -- "8. Return CIM FIELDALIAS" --> State
    
    State -- "9. Admin Approves & Deploys" --> SplunkProd

    classDef ui fill:#E60073,stroke:#fff,stroke-width:2px,color:#fff;
    classDef ai fill:#00CC66,stroke:#fff,stroke-width:2px,color:#000;
    classDef splunk fill:#222,stroke:#E60073,stroke-width:2px,color:#fff;
    
    class UI,State ui;
    class Agent,RAG ai;
    class REST,MCP,SplunkProd splunk;

For more comprehensive architectural details, see [Talon Architecture](https://godmodevegeta.github.io/splunk-talon/)
