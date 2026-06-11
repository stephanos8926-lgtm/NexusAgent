# Configuration

NexusAgent uses environment variables and a `.env` file for configuration.

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `AGENT_MODEL` | `gemini-3.1-flash-lite` | LLM model for the agent |
| `NATS_URL` | `nats://localhost:4222` | NATS server URL |
| `DB_PATH` | `nexus.db` | SQLite database path |
| `EXA_API_KEY` | — | Exa search API key |
| `TAVILY_API_KEY` | — | Tavily search API key |

## Example `.env`

```env
AGENT_MODEL=gemini-3.1-flash-lite
NATS_URL=nats://localhost:4222
DB_PATH=nexus.db
EXA_API_KEY=your-key-here
TAVILY_API_KEY=your-key-here
```
