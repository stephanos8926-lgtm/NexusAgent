# Implementation Details: Result Persistence with NATS JetStream KV (2026-06-03)

## Problem Statement
The initial result delivery mechanism used ephemeral NATS subscriptions (`tasks.results.{task_id}`). This created two critical issues:
1. **Resource Leakage**: Each result request created a persistent subscription, consuming server memory over time.
2. **At-Most-Once Delivery**: If a client was offline when a worker published a result, the result was lost.

## Solution: JetStream Key-Value Store
We transitioned to using **NATS JetStream KV**, a persistent, state-based store built on top of NATS streams.

### Architecture
- **KV Bucket**: A bucket named `nexus_results` acts as the central repository for task outcomes.
- **Write Path (Worker)**: Instead of publishing to a temporary subject, the worker now uses `kv.put(task_id, result_payload)`.
- **Read Path (SDK)**: The SDK uses `kv.get(task_id)` to fetch the result. This is a standard request-response pattern that eliminates the need for long-lived subscriptions.

### Key Advantages
- **Statelessness**: The SDK no longer needs to maintain a mapping of active subscriptions.
- **Persistence**: Results are archived on the NATS server, allowing clients to retrieve results asynchronously regardless of when they were generated.
- **Complexity Reduction**: The code for result retrieval was reduced from a complex `Future` based subscription handler to a simple KV lookup.

### Operational Impact
- Requires NATS server to be run with the `-js` flag (JetStream enabled).
- Results are persisted on the NATS server, utilizing the specified stream storage (File or Memory).
