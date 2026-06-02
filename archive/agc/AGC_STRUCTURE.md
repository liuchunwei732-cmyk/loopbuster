# Agent-Governance-Core (AGC)

AGC is an industrial-grade governance kernel for AI agents. It shifts AI execution from "disposable CLI snippets" to "governable, recoverable, and traceable Task Units."

## Core Architecture

- **`core/`**: The execution engine that manages lifecycle, state transitions, and recovery.
- **`engine/`**: The state machine scheduler providing idempotent dispatch.
- **`schemas/`**: JSON Schema contracts defining skill boundaries.
- **`storage/`**: SQLite-based audit and state persistence layer.

## TaskUnit Data Model
```typescript
interface TaskUnit {
  id: string;             // Unique audit trace
  intent: string;         // Decoupled goal
  status: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'RETRYING';
  payload: any;           // Input data
  result?: any;           // Output data
  error?: string;         // Fault isolation
  checkpoint: number;     // Resume point for deep tasks
}
```
