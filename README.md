# 🚀 FastAPI JWT LangChain AI Agent

A production-oriented AI agent backend built with **FastAPI, LangChain, Groq LLMs, JWT authentication, PostgreSQL (Neon), and Simply.com MCP integration**.

The application provides a REST API for interacting with an AI agent that dynamically selects and executes external tools using LangChain's native tool-calling architecture.

The backend integrates with Simply.com's authenticated Model Context Protocol (MCP) server, allowing the AI agent to interact with approved Simply.com account and domain-management functionality.

The companion Vue 3 Single Page Application (SPA) provides an authenticated chat interface for interacting with the agent and visualizing its workflow.

**Vue Frontend:** https://github.com/persteenolsen/vue-fastapi-jwt-auth-ai-agent-seven

---

# 📌 Project Information

- Version: 0.0.5
- Last Updated: 02-11-2026
- Python: 3.12
- Framework: FastAPI
- API Documentation: OpenAPI / Swagger
- Authentication: JWT (HS256)
- AI Framework: LangChain
- LLM Provider: Groq
- Current Model: `openai/gpt-oss-20b`
- Database: PostgreSQL (Neon)
- MCP Integration: Simply.com
- OAuth: Simply.com OAuth2
- Frontend: Future Vue 3 SPA

---

# ✨ Features

## 🔐 Authentication and Authorization

The API uses JWT-based authentication to protect endpoints.

Features:

- JWT authentication using HS256
- OAuth2-compatible password bearer authentication
- Protected API endpoints
- Bearer token authorization
- Environment-based application secrets
- Centralized authentication dependency using `verify_token`

Authentication endpoints:

- `POST /login-spa` – Login for a future Vue SPA.
- `POST /token` – Authentication for Swagger UI.

Protected endpoints require a valid JWT bearer token.

## 🤖 LangChain AI Agent

The backend uses LangChain's native tool-calling architecture.

The LLM determines whether an external tool is required to answer a question.

Agent workflow:

1. The user submits a question.
2. FastAPI receives the request.
3. LangChain processes the question.
4. Groq evaluates whether an external tool is needed.
5. The agent selects an appropriate tool.
6. The tool executes and returns an observation.
7. LangChain processes the result.
8. The agent generates the final answer.

Features:

- Native LangChain tool calling
- Automatic tool selection
- Intermediate tool-call tracking
- Structured tool inputs and observations
- Multiple external integrations
- Configurable execution limits
- Extensible tool architecture

When no external tool is required, the agent answers directly and returns an empty `actions` list.

## 🧠 Groq LLM Integration

The application uses Groq as its LLM provider.

Current model:

- `openai/gpt-oss-20b`

Configuration:

- Temperature: 0
- Streaming: Disabled
- API key managed through environment variables

## 🌐 Wikipedia Integration

The AI agent includes a Wikipedia retrieval tool.

Capabilities:

- General factual information
- Wikipedia searches
- External information retrieval
- Error handling

The agent automatically determines when Wikipedia is relevant.

## 🔗 Simply.com MCP Integration

The backend integrates with Simply.com through its authenticated Model Context Protocol (MCP) server.

MCP server:

`https://mcp.simply.com/v2`

Features:

- OAuth2 authentication
- Automatic access-token refreshing
- Persistent OAuth credentials
- Authenticated MCP connections
- Dynamic MCP tool discovery
- Read-only tool allowlist
- Integration with the LangChain agent

Currently enabled Simply.com tools:

- `list-accounts` – Retrieves Simply.com accounts.
- `list-subdomains` – Retrieves configured subdomains for a Simply.com product, including their document roots.

The `list-subdomains` tool requires a product handle (domain), for example:

`mydomainatsimply.com`

Only explicitly approved read-only tools are exposed to the AI agent.

---

# 🔑 Simply.com OAuth Architecture

Simply.com OAuth authentication is managed by the `SimplyOAuthManager` class.

OAuth credentials are stored persistently in PostgreSQL rather than relying on `.env` files.

The implementation supports:

- Initial OAuth credential storage
- Loading credentials from PostgreSQL
- Access-token management
- Automatic access-token refreshing
- Refresh-token rotation
- Persistent storage of refreshed credentials
- Token expiration tracking
- Database transactions
- PostgreSQL row locking
- Refresh synchronization across application workers

## OAuth Credential Storage

The credentials are stored in the PostgreSQL table:

`simply_oauth_credentials`

| Column | Description |
|---|---|
| `id` | Credential record identifier |
| `tokens` | OAuth access and refresh tokens (JSONB) |
| `client_info` | OAuth client registration information |
| `expires_at` | Access-token expiration timestamp |
| `updated_at` | Last credential update timestamp |

The application currently uses a single credential record with:

`id = 1`

## Automatic Token Refresh

The `SimplyOAuthManager` automatically checks whether the access token is approaching expiration.

When a refresh is required:

1. The manager obtains a PostgreSQL transaction.
2. The credential row is locked using `SELECT FOR UPDATE`.
3. The latest credentials are loaded from PostgreSQL.
4. The manager checks token expiration.
5. If necessary, a refresh request is sent to Simply.com.
6. The new access token and refresh token are persisted.
7. The expiration timestamp is updated.
8. The transaction is completed.

If Simply.com does not return a replacement refresh token, the existing refresh token is preserved.

## OAuth Status Endpoint

`GET /simply/oauth/status`

Returns information about the current OAuth authentication state:

- Authentication state
- Refresh-token availability
- Token expiration timestamp
- Remaining token lifetime
- Whether a refresh is required

Token values themselves are not exposed through the status response.

## OAuth Refresh Test Endpoint

`POST /simply/oauth/test-refresh`

A protected development/testing endpoint used to verify the Simply.com token refresh implementation.

The endpoint:

- Forces an OAuth refresh operation.
- Updates the credentials in PostgreSQL.
- Returns token status information.
- Allows verification that the expiration timestamp has changed.

**Note:** This endpoint is intended for development and testing. It should be disabled or removed before exposing the application publicly in production.

---

# 🗄️ PostgreSQL Database (Neon)

The application uses PostgreSQL hosted by Neon for persistent OAuth credential storage.

Database responsibilities:

- Persistent Simply.com OAuth credentials
- Access-token storage
- Refresh-token storage
- Token expiration tracking
- Credential update timestamps

The database connection is managed centrally through the application's database configuration.

Database connection information is stored in environment variables.

OAuth credentials are never stored directly in the application's source code.

---

# 📡 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/login-spa` | Login for future Vue SPA |
| POST | `/token` | OAuth2 login for Swagger |
| POST | `/chat` | Interact with the AI agent |
| GET | `/health` | Service health |
| GET | `/test-groq` | Test Groq connection |
| GET | `/test-wikipedia` | Test Wikipedia integration |
| GET | `/simply/oauth/status` | Simply.com OAuth status |
| POST | `/simply/oauth/test-refresh` | Force OAuth refresh for testing |
| GET | `/simply/accounts` | List Simply.com accounts |
| GET | `/simply/subdomains/{domain}` | List product subdomains |

Protected endpoints require a valid JWT bearer token.

---

# 📦 Chat Response Model

The chat endpoint returns a structured response containing the agent's actions and final answer.

Example when a tool is used:

    {
      "response": {
        "actions": [
          {
            "action": "list-subdomains",
            "action_input": {
              "domain": "persteenolsen.com"
            },
            "observation": "Retrieved subdomain information..."
          }
        ],
        "final_answer": "Here are the configured subdomains..."
      }
    }

Example when no tool is needed:

    {
      "response": {
        "actions": [],
        "final_answer": "Here is the answer to your question."
      }
    }

---

# ⚙️ Getting Started

Clone the repository:

    git clone https://github.com/your-username/your-repository.git

Enter the backend project:

    cd backend

Create a virtual environment:

Windows:

    python -m venv .venv
    .venv\Scripts\activate

Linux/macOS:

    python -m venv .venv
    source .venv/bin/activate

Install dependencies:

    pip install -r requirements.txt

---

# 🔑 Environment Variables

Create a `.env` file in the project root.

Example configuration:

    SECRET_KEY=your_secret_key_here
    GROQ_API_KEY=your_groq_api_key
    DATABASE_URL=your_neon_postgresql_connection_string
    FAKE_USERNAME=admin
    FAKE_PASSWORD=your_password

Simply.com OAuth credentials are initialized and stored in PostgreSQL.

The application loads Simply.com OAuth credentials from the `simply_oauth_credentials` database table.

Do not store production OAuth tokens directly in `.env`.

Generate a secret key:

    python -c "import secrets; print(secrets.token_hex(32))"

**Important:** Never commit `.env` files, database connection strings, API keys, JWT secrets, or OAuth tokens to GitHub.

---

# Initialize Simply.com OAuth

This should:

Connect to your Neon PostgreSQL database

Perform the initial Simply.com OAuth authorization

Create/store the credentials or tokens in PostgreSQL

From the root of the powershell run:

python -m integrations.initial_simply_oauth

Make sure that initial auth towards have been completed!

There must be tokens / credentials in the PostgreSQL!

---

# ▶️ Running the Application

Make sure that initial auth towards have been completed!

There must be tokens / credentials in the PostgreSQL!

If there is no valid credentials / row in the PostgreSQL, then run:

python -m integrations.initial_simply_oauth

That will perform the initial auth towards simply MCP

Start the FastAPI backend:

    uvicorn main:app --reload

Local API:

    http://127.0.0.1:8000

Swagger documentation:

    http://127.0.0.1:8000/docs

OpenAPI schema:

    http://127.0.0.1:8000/openapi.json

---

# 🔐 Authentication Flow

## Swagger Authentication

1. Open `/docs`.
2. Select the Authorize button.
3. Authenticate through `/token`.
4. Swagger stores the JWT bearer token.
5. Use the protected API endpoints.

## Future Vue SPA Authentication

1. Login using `/login-spa`.
2. Receive a JWT.
3. Store the token securely.
4. Include the authorization header in API requests:

       Authorization: Bearer <token>

5. Access protected endpoints, including `/chat`.

---
```
# 🧠 Agent Workflow

    User Question
          |
          v
      Future Vue 3 Frontend
          |
          v
      FastAPI Backend
          |
          v
     JWT Authentication
          |
          v
      LangChain Agent
          |
       Groq LLM
          |
      +---+---+
      |       |
   Wikipedia  Simply.com MCP
      |       |
      +---+---+
          |
      Tool Observation
          |
          v
      Final Answer
          |
          v
       API Response
```
The agent selects the appropriate tool based on the user's question.

If no external information is required, the LLM answers directly.

Simply.com MCP requests use the shared OAuth manager to obtain valid access tokens.

---

# 🏗️ Architecture

The application combines a FastAPI backend with a planned Vue 3 frontend.

## Backend Responsibilities

- Authentication and JWT validation
- API endpoint management
- LangChain agent orchestration
- Groq LLM integration
- Wikipedia retrieval
- Simply.com OAuth management
- PostgreSQL credential persistence
- Simply.com MCP tool discovery and execution
- Protected external service integrations

## Frontend Responsibilities

The Vue 3 application provides:

- JWT authentication
- Chat interface
- Pinia state management
- API integration
- Display of final answers
- Display of agent actions
- Display of tool inputs and observations
- Transparent agent workflow

The AI agent is responsible for selecting tools, interpreting their results, and generating the final answer.

---

# 💬 Example Requests

## General Question

Request:

    {
      "message": "Tell me a joke"
    }

The agent answers directly without using an external tool.

## Wikipedia

Request:

    {
      "message": "Who is the CEO of Apple?"
    }

The agent can select Wikipedia to retrieve relevant information.

## Simply.com Accounts

Request:

    {
      "message": "List my Simply.com accounts"
    }

The agent selects `list-accounts`.

## Simply.com Subdomains

Request:

    {
      "message": "List the subdomains for mydomainatsimply.com"
    }

The agent selects `list-subdomains` and supplies the domain argument.

---

# 🧪 Testing and Diagnostics

The project includes diagnostic functionality for verifying external integrations.

## Simply.com OAuth Discovery

A standalone discovery script can inspect Simply.com's OAuth metadata.

It checks:

- Protected resource metadata
- Authorization server discovery
- Authorization endpoints
- Token endpoints
- Supported OAuth grant types
- Refresh-token grant support

This is a diagnostic script and does not participate in normal application execution.

## Simply.com OAuth Refresh

The protected endpoint:

`POST /simply/oauth/test-refresh`

Can be used to verify:

- Successful access-token refresh
- Refresh-token availability
- PostgreSQL persistence
- Updated expiration timestamp
- Updated database modification timestamp

## Neon Database Verification

The OAuth credential record can be inspected in the Neon SQL Editor.

Example query:

    SELECT
        id,
        expires_at,
        updated_at,
        tokens->>'access_token' IS NOT NULL AS has_access_token,
        tokens->>'refresh_token' IS NOT NULL AS has_refresh_token
    FROM simply_oauth_credentials
    WHERE id = 1;

The query verifies that both tokens exist and that the expiration and update timestamps are maintained.

Never retrieve or display actual token values when performing routine diagnostics.

---

# 🚧 Current Limitations

- No conversation memory
- No streaming responses
- Demo authentication system
- Single-agent workflow
- Limited Simply.com tools enabled through the read-only allowlist
- Single Simply.com OAuth credential record

---

# 🚀 Future Improvements

- Conversation memory
- Streaming responses
- Additional Simply.com MCP tools
- Multi-agent workflows
- Persistent user sessions
- Production-grade authentication
- Monitoring and observability
- Improved error handling
- Expanded automated testing

---

# 💡 Design Philosophy

> Use structured AI agent workflows instead of fragile prompt parsing.

Main goals:

- Reliability
- Transparency
- Maintainability
- Simple architecture
- Easy extension
- Clear separation of responsibilities
- Secure credential management

---

# 🙌 Final Notes

This project demonstrates how FastAPI, OpenAPI / Swagger, JWT authentication, LangChain, Groq LLMs, PostgreSQL, Neon, and Simply.com MCP integration can be combined to create a modern AI agent backend.

The backend exposes a REST API while a companion Vue 3 SPA provides an authenticated interface for interacting with the AI agent and visualizing its workflow.

Simply.com OAuth credentials are persisted in PostgreSQL, with automatic token refreshing and synchronized database updates.

The architecture is designed to be modular and extensible, allowing additional tools, integrations, and frontend functionality to be added over time.

---

# 📄 License

MIT License