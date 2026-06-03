# ADR 0001: NexusTelemetry System Design

## 1. Status
Accepted

## 2. Context
To develop NexusAgent into an enterprise-grade solution, a robust and standardized logging and telemetry system is essential. The current project lacks a formal approach to log management, structured logging, dynamic verbosity control, and integration with system-level logging mechanisms like Systemd Journald.

Key drivers for this decision include:
- **Improved Observability:** Enable rapid debugging, performance monitoring, and security auditing across all components (server, SDK, clients).
- **Centralized Log Management:** Facilitate collection and analysis of logs in development and production environments, leveraging existing infrastructure like `journald`.
- **Maintainability:** Reduce ad-hoc logging, ensuring consistent log formats and information capture.
- **Compliance & Security:** Provide auditable log trails for security events and access control.
- **Collaboration:** Standardize logging practices for multiple developers/agents.

## 3. Decision
We will implement a dedicated `NexusTelemetry` library (in `src/nexustele/`) to provide structured, channel-based logging with configurable verbosity and integration with Systemd Journald. This library will serve as the single source for all logging within NexusAgent.

### 3.1. Core Library
A new Python package `src/nexustele/` will be created with the following core components:
- `models.py`: Pydantic schemas for `LogEntry` to ensure structured, consistent log data.
- `config.py`: `TelemetryConfig` for centralized configuration of log levels, subscribers, and modes.
- `channels.py`: Defines standard logging channels (e.g., `INFO`, `WARNING`, `ERROR`, `DEBUG`, `AUDIT`, `SECURITY`, `ACCESS_LOG`).
- `context.py`: Manages contextual information (e.g., `correlation_id` for request tracing).
- `subscribers.py`: Defines a `BaseSubscriber` interface and concrete implementations (`ConsoleSubscriber` for stdout/stderr, `JournaldSubscriber` for Systemd Journald).
- `emitter.py`: The central `NexusTelemetryEmitter` that processes `LogEntry` objects and dispatches them to active subscribers.

### 3.2. Structured Logging with `structlog`
`structlog` will be integrated to ensure all log output is structured (JSON format in production, human-readable in development). This allows for efficient machine parsing and querying of logs.

### 3.3. Build Mode & Runtime Debugging
- **Build Modes:** Controlled by the `NEXUS_MODE` environment variable (`DEVELOPMENT` or `PRODUCTION`), affecting default log levels (e.g., `DEBUG` channel suppressed in `PRODUCTION`).
- **Runtime Debugging:** A `NEXUS_DEBUG=true` environment variable will force the `DEBUG` channel to be active across all subscribers, enabling on-the-fly troubleshooting without redeployment.

### 3.4. API Exposure & SDK Integration
- **`NexusSDK`:** The `src/nexusagent/clients/sdk.py` will expose `NexusTelemetryEmitter` methods (e.g., `sdk.log.info()`) for consistent client-side logging.
- **FastAPI:** A FastAPI middleware will automatically capture request/response data for `ACCESS_LOG`. A `/telemetry/logs` API endpoint (initially a placeholder) will provide a future mechanism for external log access.

### 3.5. Systemd Journald Integration
The `JournaldSubscriber` will use Python's standard `logging.handlers.SysLogHandler` to send structured log messages (formatted as JSON by `structlog`) to the local Systemd Journald socket (`/dev/log`), ensuring central system logging integration.

## 4. Alternatives Considered
- **Basic `python-logging` only:** Rejected for lack of native structured logging capabilities, making log analysis cumbersome for an enterprise system.
- **Full `opentelemetry` tracing:** While valuable, full distributed tracing and metrics are more complex to implement and were deferred to a later phase to prioritize robust, structured logging initially.
- **Separate logging libraries for client/server:** Rejected for lack of consistency and increased maintenance overhead; a single `NexusTelemetry` library ensures uniformity.

## 5. Consequences
- **Positive:** Significant improvement in system observability, diagnostics, and troubleshooting capabilities. Standardized log formats enhance automated analysis and compliance efforts. Consistent logging practices improve developer productivity and code quality. Foundation laid for future integration with advanced telemetry systems.
- **Negative:** Requires an initial development effort to build out the `NexusTelemetry` library and integrate it across existing components. Adds `structlog` as a dependency. Requires adherence to new logging patterns by all developers.
