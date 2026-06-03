# Technical Specification: NexusTelemetry System Implementation

## 1. Introduction
This document specifies the technical design and implementation details for the `NexusTelemetry` library. This system is crucial for providing robust, reusable, and configurable logging and telemetry capabilities across both server and client components of NexusAgent.

**Goals:**
- Implement a dedicated `NexusTelemetry` library for structured logging.
- Support dynamic, channel-based logging (INFO, WARN, ERROR, DEBUG, AUDIT, SECURITY, ACCESS_LOG).
- Provide multi-mode verbosity: configurable at build-time (DEVELOPMENT/PRODUCTION) and dynamic at runtime (DEBUG flag).
- Seamlessly integrate with Systemd `journald` for system-wide log collection.
- Expose logging functionalities via the `NexusSDK` and a dedicated FastAPI API endpoint.
- Ensure consistent log schemas across the entire system.

**Non-Goals:**
- Full-fledged distributed tracing with OpenTelemetry beyond basic correlation IDs (planned for future phases due to complexity).
- Advanced metrics collection and aggregation (planned for future phases).
- A GUI-based log viewer or management system as part of this phase.

## 2. Technical Design

### 2.1. Core Library (`src/nexustele`)
The `nexustele` package will be a standalone Python library within `src/`, designed for high reusability.

#### 2.1.1. `src/nexustele/models.py` - Log Schemas
Define Pydantic models for structured log events, ensuring consistency.

```python
# src/nexustele/models.py
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime

class LogEntry(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    level: str
    channel: str
    event: str
    service: Optional[str] = None
    module: Optional[str] = None
    correlation_id: Optional[str] = None
    user_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    # Add fields for build/runtime modes
    build_mode: Optional[str] = None
    debug_mode: bool = False
```

#### 2.1.2. `src/nexustele/config.py` - Telemetry Configuration
Defines the configuration schema for `NexusTelemetry`, loaded at application start.

```python
# src/nexustele/config.py
from pydantic import BaseModel
from typing import Dict, List, Literal

class TelemetryConfig(BaseModel):
    default_log_level: Literal["INFO", "WARNING", "ERROR", "DEBUG"] = "INFO"
    build_mode_log_levels: Dict[str, Dict[str, str]] = {
        "DEVELOPMENT": {
            "INFO": "INFO", "WARN": "WARNING", "ERROR": "ERROR",
            "DEBUG": "DEBUG", "AUDIT": "INFO", "SECURITY": "INFO",
            "ACCESS_LOG": "INFO"
        },
        "PRODUCTION": {
            "INFO": "WARNING", "WARN": "WARNING", "ERROR": "ERROR",
            "DEBUG": "CRITICAL", # DEBUG channel effectively disabled in PROD by default
            "AUDIT": "INFO", "SECURITY": "WARNING", "ACCESS_LOG": "INFO"
        }
    }
    # Future: enable/disable specific subscribers
    enable_console_subscriber: bool = True
    enable_journald_subscriber: bool = True
    # Default log levels for each channel when debug is OFF
    channel_default_levels: Dict[str, str] = {
        "INFO": "INFO",
        "WARN": "WARNING",
        "ERROR": "ERROR",
        "DEBUG": "DEBUG",
        "AUDIT": "INFO",
        "SECURITY": "WARNING",
        "ACCESS_LOG": "INFO"
    }
```

#### 2.1.3. `src/nexustele/channels.py` - Channel Definitions
Defines a central registry for log channels.

```python
# src/nexustele/channels.py
from typing import List

class LogChannels:
    INFO = "INFO"
    WARNING = "WARN"
    ERROR = "ERROR"
    DEBUG = "DEBUG"
    AUDIT = "AUDIT"
    SECURITY = "SECURITY"
    ACCESS_LOG = "ACCESS_LOG"
    
    @classmethod
    def all(cls) -> List[str]:
        return [
            cls.INFO, cls.WARNING, cls.ERROR, cls.DEBUG,
            cls.AUDIT, cls.SECURITY, cls.ACCESS_LOG
        ]
```

#### 2.1.4. `src/nexustele/subscribers.py` - Log Subscribers/Handlers
Defines interfaces and concrete implementations for log output.

**`BaseSubscriber` Interface:**
```python
# src/nexustele/subscribers.py (excerpt)
from abc import ABC, abstractmethod
from src.nexustele.models import LogEntry

class BaseSubscriber(ABC):
    @abstractmethod
    def emit(self, entry: LogEntry):
        pass
```

**`ConsoleSubscriber`:** Prints human-readable logs to `stdout`/`stderr`.
```python
# src/nexustele/subscribers.py (excerpt)
import logging
import structlog
import os
from src.nexustele.config import TelemetryConfig
from src.nexustele.models import LogEntry

class ConsoleSubscriber(BaseSubscriber):
    def __init__(self, config: TelemetryConfig, build_mode: str, debug_mode: bool):
        # Configure structlog
        self.config = config
        self.build_mode = build_mode
        self.debug_mode = debug_mode
        self.log_level_map = {
            "CRITICAL": logging.CRITICAL,
            "ERROR": logging.ERROR,
            "WARNING": logging.WARNING,
            "INFO": logging.INFO,
            "DEBUG": logging.DEBUG,
            "NOTSET": logging.NOTSET,
        }
        
        # Get base log level based on build mode for the channel, default to INFO if not found
        base_level_str = config.build_mode_log_levels.get(build_mode, {}).get("INFO", "INFO")
        if self.debug_mode:
            # If debug mode is on, force console to DEBUG level for all messages
            level = logging.DEBUG
        else:
            level = self.log_level_map.get(base_level_str.upper(), logging.INFO);

        # Basic standard logging setup for console
        logging.basicConfig(level=level, format="%(message)s")

        # Configure structlog processors for console output
        if build_mode == "DEVELOPMENT" or debug_mode:
            self.processors = [
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M.%S"),
                structlog.processors.StackInfoRenderer(),
                structlog.dev.ConsoleRenderer() # Pretty printing for development
            ]
        else:
            self.processors = [
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.JSONRenderer() # JSON output for production
            ]

        structlog.configure(
            processors=self.processors,
            wrapper_class=structlog.stdlib.BoundLogger,
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=False,
        )
        self._logger = structlog.get_logger(__name__)


    def emit(self, entry: LogEntry):
        # Map log entry level to structlog method
        log_method = getattr(self._logger, entry.level.lower(), self._logger.info)
        
        # Extract metadata and ensure all log entry fields are passed
        log_data = entry.model_dump(exclude_unset=True, exclude={'metadata'})
        # Merge direct metadata from LogEntry, overwriting if keys conflict
        combined_metadata = {**log_data, **entry.metadata}

        log_method(entry.event, **combined_metadata)

```

**`JournaldSubscriber`:** Integrates with Systemd Journald. Uses Python's standard `logging` `SysLogHandler`.
```python
# src/nexustele/subscribers.py (excerpt)
import logging
import structlog
import os
from logging.handlers import SysLogHandler
import json
from src.nexustele.models import LogEntry
from src.nexustele.config import TelemetryConfig

class JournaldSubscriber(BaseSubscriber):
    def __init__(self, config: TelemetryConfig, build_mode: str, debug_mode: bool):
        self.config = config
        self.build_mode = build_mode
        self.debug_mode = debug_mode
        self.log_level_map = {
            "CRITICAL": logging.CRITICAL,
            "ERROR": logging.ERROR,
            "WARNING": logging.WARNING,
            "INFO": logging.INFO,
            "DEBUG": logging.DEBUG,
            "NOTSET": logging.NOTSET,
        }

        # Determine log level for journald
        base_level_str = config.build_mode_log_levels.get(build_mode, {}).get("INFO", "INFO")
        if self.debug_mode:
            level = logging.DEBUG
        else:
            level = self.log_level_map.get(base_level_str.upper(), logging.INFO)

        # Basic Python logging setup for SysLogHandler
        self.logger = logging.getLogger("journald_logger")
        self.logger.setLevel(level);
        
        # Ensure only one handler
        if not self.logger.handlers:
            # Using /dev/log is the standard way to send to journald via syslog socket
            handler = SysLogHandler(address="/dev/log") 
            # A formatter that outputs JSON for journald to parse structured data
            formatter = logging.Formatter('%(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

        # Configure structlog processors for JSON output for Journald
        self.processors = [
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            # Remove metadata to avoid duplication; it will be in the dict directly
            structlog.processors.dict_tracebacks, 
            structlog.processors.JSONRenderer() 
        ]
        
        # Need to use a different structlog logger than console, or configure independently
        # For simplicity, this will emit via standard logger after structuring
        self._structlog_logger = structlog.get_logger("journald_structlog", wrapper_class=structlog.stdlib.BoundLogger)
        
    def emit(self, entry: LogEntry):
        if not self.logger.isEnabledFor(self.log_level_map.get(entry.level.upper(), logging.INFO)):
            return # Don't emit if level is too low

        log_data = entry.model_dump(exclude_unset=True, exclude={'metadata'})
        combined_metadata = {**log_data, **entry.metadata}

        # Structlog processes dict to JSON string for SysLogHandler
        processed_event = structlog.stdlib.ProcessorFormatter.format_exc_info(
            {
                "event": entry.event, 
                "logger": entry.service or __name__, # Default logger name if not set
                "level": entry.level.lower(),
                **combined_metadata
            }, 
            self.processors # Pass structlog processors here
        )
        
        # Use a simple formatter that directly passes the JSON string to syslog
        # The syslog handler will then send this to journald
        # We need to map LogEntry level to standard logging levels
        standard_level = self.log_level_map.get(entry.level.upper(), logging.INFO)
        self.logger.log(standard_level, processed_event)
```

**`FileSubscriber` (Future)**: Writes logs to rotating files (placeholder for now).

#### 2.1.5. `src/nexustele/context.py` - Context Management
Manages request-specific log context (e.g., correlation IDs).

```python
# src/nexustele/context.py
import contextvars
from typing import Optional

# Context variable for storing the current request ID or correlation ID
correlation_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("correlation_id", default=None)

def set_correlation_id(correlation_id: str):
    correlation_id_var.set(correlation_id)

def get_correlation_id() -> Optional[str]:
    return correlation_id_var.get()
```

#### 2.1.6. `src/nexustele/emitter.py` - Core Emitter
The central dispatch for log events.

```python
# src/nexustele/emitter.py
import os
import sys
from typing import Dict, List, Any, Literal
from src.nexustele.models import LogEntry
from src.nexustele.channels import LogChannels
from src.nexustele.subscribers import BaseSubscriber, ConsoleSubscriber, JournaldSubscriber # , FileSubscriber
from src.nexustele.config import TelemetryConfig
from src.nexustele.context import get_correlation_id

class NexusTelemetryEmitter:
    def __init__(self, config: TelemetryConfig = TelemetryConfig()):
        self.config = config
        self.subscribers: List[BaseSubscriber] = []
        self._is_initialized = False

        # Determine build and debug modes from environment variables
        self.build_mode = os.getenv("NEXUS_MODE", "DEVELOPMENT").upper()
        self.debug_mode = os.getenv("NEXUS_DEBUG", "false").lower() == "true"

        self._initialize_subscribers()

    def _initialize_subscribers(self):
        if self._is_initialized:
            return

        if self.config.enable_console_subscriber:
            self.add_subscriber(ConsoleSubscriber(self.config, self.build_mode, self.debug_mode))
        if self.config.enable_journald_subscriber:
            # Check if /dev/log exists for journald/syslog integration
            if os.path.exists("/dev/log"):
                self.add_subscriber(JournaldSubscriber(self.config, self.build_mode, self.debug_mode))
            else:
                print("Warning: /dev/log not found. JournaldSubscriber not enabled.", file=sys.stderr)
        # Add other subscribers (e.g., FileSubscriber) here as they are implemented

        self._is_initialized = True

    def add_subscriber(self, subscriber: BaseSubscriber):
        self.subscribers.append(subscriber)

    def log(
        self,
        level: Literal["INFO", "WARN", "ERROR", "DEBUG", "AUDIT", "SECURITY", "ACCESS_LOG"],
        event: str,
        channel: Optional[str] = None,
        service: Optional[str] = None,
        module: Optional[str] = None,
        user_id: Optional[str] = None,
        **kwargs: Any
    ):
        if not self._is_initialized:
            self._initialize_subscribers()

        actual_channel = channel if channel else level # Default channel is the level

        # Determine effective log level for the channel based on mode
        # Fallback to DEVELOPMENT if build_mode not found, then to INFO for the specific channel
        mode_log_levels = self.config.build_mode_log_levels.get(self.build_mode, self.config.build_mode_log_levels["DEVELOPMENT"])
        effective_level_for_channel_str = mode_log_levels.get(actual_channel.upper(), self.config.channel_default_levels.get(actual_channel.upper(), "INFO"))


        # Only emit DEBUG messages if debug_mode is true or the effective level explicitly allows it
        if actual_channel.upper() == LogChannels.DEBUG:
            if not self.debug_mode and effective_level_for_channel_str == "CRITICAL": # If debug_mode is off and explicitly disabled
                 return
            elif not self.debug_mode and effective_level_for_channel_str not in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
                # If debug mode is off and the channel's effective level isn't DEBUG/INFO/WARN/ERROR/CRITICAL, suppress.
                return

        correlation_id = get_correlation_id() # Get correlation ID from context

        entry = LogEntry(
            level=effective_level_for_channel_str,
            channel=actual_channel,
            event=event,
            service=service,
            module=module,
            correlation_id=correlation_id,
            user_id=user_id,
            metadata=kwargs,
            build_mode=self.build_mode,
            debug_mode=self.debug_mode
        )

        for subscriber in self.subscribers:
            subscriber.emit(entry)

    def info(self, event: str, **kwargs):
        self.log(LogChannels.INFO, event, **kwargs)

    def warn(self, event: str, **kwargs):
        self.log(LogChannels.WARNING, event, **kwargs)

    def error(self, event: str, **kwargs):
        self.log(LogChannels.ERROR, event, **kwargs)

    def debug(self, event: str, **kwargs):
        self.log(LogChannels.DEBUG, event, **kwargs)

    def audit(self, event: str, **kwargs):
        self.log(LogChannels.AUDIT, event, channel=LogChannels.AUDIT, **kwargs)

    def security(self, event: str, **kwargs):
        self.log(LogChannels.SECURITY, event, channel=LogChannels.SECURITY, **kwargs)

    def access(self, event: str, **kwargs):
        self.log(LogChannels.ACCESS_LOG, event, channel=LogChannels.ACCESS_LOG, **kwargs)

# Global emitter instance
nexus_telemetry_emitter = NexusTelemetryEmitter()
```

#### 2.1.7. `src/nexustele/__init__.py`
Exports the core emitter.

```python
# src/nexustele/__init__.py
from .emitter import nexus_telemetry_emitter
from .models import LogEntry
from .config import TelemetryConfig
from .channels import LogChannels
from .context import set_correlation_id, get_correlation_id
```

### 2.2. Build & Runtime Modes

*   **Build-time Configuration:** Environment variable `NEXUS_MODE` will be set to `DEVELOPMENT` or `PRODUCTION` (default `DEVELOPMENT`). This directly impacts `TelemetryConfig`'s `build_mode_log_levels`.
*   **Runtime Debug Flag:** Environment variable `NEXUS_DEBUG` (set to `true` or `false`, default `false`). If `true`, the `DEBUG` channel is force-activated across all subscribers, overriding normal log level filtering for that channel.

### 2.3. API Exposure & SDK Integration

#### 2.3.1. `NexusSDK` Integration (`src/nexusagent/sdk.py`)
The `NexusSDK` will hold an instance of `NexusTelemetryEmitter` to allow client-side components to emit logs.

```python
# src/nexusagent/sdk.py (modifications)
# ... existing imports
import uuid
import asyncio
from nexusagent.models import TaskSchema, ResultSchema # Assumes TaskSchema, ResultSchema are defined here
from nexusagent.auth import AuthManager # Assumes AuthManager is defined here
from nexusagent.bus import AgentBus # Assumes AgentBus is defined here
from nexusagent.config import load_config # Assumes load_config is defined here
from src.nexustele.emitter import nexus_telemetry_emitter
from src.nexustele.context import set_correlation_id

class NexusSDK:
    def __init__(self):
        # ... existing initializations
        self.auth = AuthManager()
        self.config = load_config()
        self.bus = AgentBus(url=self.config.nats_url)
        self.log = nexus_telemetry_emitter # Expose the emitter directly

    def submit_task(self, task: TaskSchema) -> ResultSchema:
        # Generate and set a correlation ID for the task lifecycle
        correlation_id = str(uuid.uuid4())
        set_correlation_id(correlation_id) # Set for this context

        self.log.info(f"Task {task.id} submitted via SDK.", task_id=task.id, correlation_id=correlation_id)
        # Auth check
        try:
            self.auth.get_api_key("nats_service")
            self.log.security("Authentication check successful for NATS service.", service="nats_service", correlation_id=correlation_id)
        except ValueError as e:
            self.log.error(f"Authentication failed for NATS service: {e}", service="nats_service", error_detail=str(e), correlation_id=correlation_id)
            return ResultSchema(success=False, error=f"Authentication failed: {e}")

        asyncio.run(self._publish_task(task))
        self.log.info(f"Task {task.id} published to NATS.", task_id=task.id, correlation_id=correlation_id)
        return ResultSchema(success=True, data=f"Task {task.id} submitted")

    async def _publish_task(self, task: TaskSchema):
        # ... existing NATS publish logic
        self.log.debug(f"Attempting to connect to NATS at {self.config.nats_url}", url=self.config.nats_url)
        await self.bus.connect()
        self.log.debug(f"Connected to NATS, publishing task.new for {task.id}", task_id=task.id)
        await self.bus.publish("task.new", task.description)
        await self.bus.close()
        self.log.debug(f"NATS connection closed after publishing task {task.id}", task_id=task.id)
        
    def get_status(self, task_id: str) -> str:
        self.log.info(f"Fetching status for task {task_id}", task_id=task_id)
        # Status check logic (simulated for now)
        return "pending"
```

#### 2.3.2. FastAPI Middleware (`src/nexusagent/server/middleware.py`)
A new file will be created for FastAPI middleware that logs access and sets correlation IDs.

```python
# src/nexusagent/server/middleware.py (New file)
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp
import uuid
from src.nexustele.emitter import nexus_telemetry_emitter
from src.nexustele.context import set_correlation_id

class TelemetryMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        correlation_id = str(uuid.uuid4())
        set_correlation_id(correlation_id)

        nexus_telemetry_emitter.access(
            "Incoming request",
            method=request.method,
            path=request.url.path,
            client_ip=request.client.host if request.client else "unknown",
            correlation_id=correlation_id
        )

        response = await call_next(request)

        nexus_telemetry_emitter.access(
            "Outgoing response",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            correlation_id=correlation_id
        )
        return response

```

#### 2.3.3. FastAPI Server Updates (`src/nexusagent/server.py`)
Integrate the middleware and dependency injection.

```python
# src/nexusagent/server.py (modifications)
from fastapi import FastAPI, Depends, Request
from nexusagent.sdk import NexusSDK
from nexusagent.models import TaskSchema, ResultSchema
from src.nexustele.emitter import nexus_telemetry_emitter # Import global emitter
from src.nexustele.context import get_correlation_id
from src.nexusagent.server.middleware import TelemetryMiddleware # New Middleware

app = FastAPI()
app.add_middleware(TelemetryMiddleware) # Add the telemetry middleware
sdk = NexusSDK()

# Dependency for injecting a contextual logger
def get_logger(request: Request):
    # This will return a bound logger that includes request context if desired
    # For now, we return the global emitter; contextvars handles correlation_id
    return nexus_telemetry_emitter

@app.post("/tasks", response_model=ResultSchema)
async def create_task(task: TaskSchema, logger = Depends(get_logger)):
    logger.info(f"Received task via API: {task.id}", task_id=task.id)
    # The SDK's submit_task will also log, maintaining the correlation_id context
    result = sdk.submit_task(task)
    if not result.success:
        logger.error(f"Task submission failed for {task.id}: {result.error}", task_id=task.id, error=result.error)
    return result

@app.get("/tasks/{task_id}")
async def get_task_status(task_id: str, logger = Depends(get_logger)):
    logger.info(f"API: Fetching status for task {task_id}", task_id=task_id)
    return {"status": sdk.get_status(task_id)}

# New API endpoint for fetching logs (controlled by authentication/authorization)
@app.get("/telemetry/logs")
async def get_telemetry_logs(request: Request, logger = Depends(get_logger)):
    # TODO: Implement authentication and authorization for this endpoint
    # For now, it's a placeholder. In a real system, you'd fetch from a log store.
    logger.security("Attempt to access telemetry logs API.", client_ip=request.client.host if request.client else "unknown")
    return {"message": "Log retrieval API is a placeholder for a future log storage backend."}

```

### 2.4. Journald Integration
The `JournaldSubscriber` detailed in Section 2.1.4 utilizes Python's `logging.handlers.SysLogHandler` pointing to `/dev/log`. `structlog` is configured with a JSON renderer when emitting to this subscriber to ensure structured logs are passed, which `journald` can then ingest and query effectively. Log levels are dynamically adjusted based on `NEXUS_MODE` and `NEXUS_DEBUG`.

### 2.5. Error Handling & Detection
The `NexusTelemetry` system inherently improves error detection by standardizing `ERROR` level logs and allowing easy filtering. Error handling within the telemetry system itself:
*   Subscribers operate independently; a failure in one won't stop others.
*   The `ConsoleSubscriber` is always a fallback.
*   Future: `try-except` blocks around subscriber `emit` calls to catch and report internal telemetry errors without crashing the main application flow.

## 3. Naming Conventions

*   **Log Levels/Channels:** Standard constants (`INFO`, `WARN`, `ERROR`, `DEBUG`, `AUDIT`, `SECURITY`, `ACCESS_LOG`) from `src/nexustele/channels.py`.
*   **Structured Log Fields:** Consistent keys for `LogEntry` (e.g., `timestamp`, `level`, `channel`, `event`, `service`, `module`, `correlation_id`, `user_id`, `metadata`). `metadata` is a flexible `dict` for additional context.
*   **Error Messages:** Should be clear, concise, and ideally follow a `[ERROR_CODE] - Description` pattern for easier parsing and alarming.

## 4. Testing Strategy
*   **Unit Tests (`tests/unit/nexustele/`):**
    *   Test `LogEntry` schema validation.
    *   Test `TelemetryConfig` loading and default values.
    *   Test `Emitter` dispatch logic (correctly routes logs to subscribers based on levels and channels).
    *   Test `ConsoleSubscriber` output formatting (human-readable vs. JSON based on mode).
    *   Test `JournaldSubscriber` interaction with `SysLogHandler` (mock `SysLogHandler`).
    *   Test `context.py` for `correlation_id` management.
    *   Test mode-based verbosity (e.g., `DEBUG` channel logs only in debug mode, or different levels in PROD vs. DEV).
*   **Integration Tests (`tests/integration/`):**
    *   FastAPI Middleware: Verify access logs are emitted, `correlation_id` is set for each request/response cycle.
    *   SDK: Ensure SDK logging methods correctly emit structured logs with context.
    *   End-to-End Test (see separate Tech Spec for E2E): Verify the entire chain from client -> SDK -> FastAPI -> NATS (simulated) -> `Journald`.

## 5. Phased Rollout
This technical specification details the implementation for **Phase 4: Implement NexusTelemetry Library** and its initial integration steps in **Phase 5: Integrate NexusTelemetry into NexusAgent Core**. Testing (Phase 6) and documentation (Phase 7) will follow.
