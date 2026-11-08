/** Transport/types only. Rendering and native desktop integration belong to the overlay. */
export type Effect = "read" | "navigate" | "edit" | "submit" | "send" | "delete" | "purchase";
export type Scope = { app: string; url: string | null };
export type Point = { x: number; y: number };
export type ComputerAction =
  | ({ type: "click"; button: "left" | "right" | "wheel" | "back" | "forward"; keys?: string[] } & Point)
  | ({ type: "double_click" | "move"; keys?: string[] } & Point)
  | ({ type: "scroll"; scroll_x: number; scroll_y: number; keys?: string[] } & Point)
  | { type: "drag"; path: Point[]; keys?: string[] }
  | { type: "keypress"; keys: string[] }
  | { type: "type"; text: string }
  | { type: "wait" };
export type Criterion = { id: string; description: string };
export type TaskInput = {
  mode: "live" | "rehearsal";
  task_family: string;
  goal: string;
  deadline: string; // ISO 8601 with timezone
  context: string;
  allowed_apps: string[]; // Host's canonical app identifiers
  allowed_domains: string[]; // Exact hostnames, no wildcard/scheme/port
  allowed_effects: Effect[];
  success_criteria: Criterion[];
  reserve_seconds?: number;
};
export type Plan = {
  summary: string;
  fallback: string;
  steps: { title: string; kind: "inspect" | "prepare" | "act" | "commit" | "verify"; required: boolean }[];
};
export type ComputerRequest = { id: string } & (
  | { operation: "screenshot"; arguments: Record<string, never> }
  | { operation: "preflight"; arguments: { action: ComputerAction } }
  | { operation: "execute"; arguments: { action: ComputerAction; preflight_token: string; state_id: string } }
  | { operation: "verify"; arguments: { criteria: Criterion[] } }
);
export type ComputerResult =
  | { image_url: string; width: number; height: number; scope: Scope }
  | { allowed: boolean; effect?: Effect; scope: Scope; token?: string; state_id?: string; summary?: string }
  | { executed: boolean; scope: Scope; state_id: string }
  | { checks: { id: string; passed: boolean; evidence: string }[] }
  | { error: string };
export type Approval = {
  id: string; effect: Effect | "api_safety"; summary: string; state_id: string;
  action?: ComputerAction; checks?: { id: string; code?: string; message?: string }[];
};
export type Status = "created" | "planning" | "running" | "verifying" | "waiting_input" |
  "completed" | "handoff" | "cancelled" | "failed" | "deadline_stopped";
export type Snapshot = {
  id: string; status: Status; mode: "live" | "rehearsal"; goal: string; deadline: string;
  seconds_remaining: number; reserve_seconds: number; action_count: number; plan: Plan | null;
  verification: { checks: { id: string; passed: boolean; evidence: string }[] } | null;
  pending_computer_request: ComputerRequest | null; pending_approval: Approval | null; event_cursor: number;
  model?: { provider: string; policy_model: string; computer_model: string; key_configured: boolean; reasoning_effort: string };
};
export type Event = { seq: number; type: string; at: number; data: Record<string, unknown> };

export class OverlayAIClient {
  constructor(private baseURL: string, private token: string) {}

  private async request<T>(path: string, body?: unknown, signal?: AbortSignal): Promise<T> {
    const response = await fetch(this.baseURL + path, {
      method: body === undefined ? "GET" : "POST",
      headers: { Authorization: `Bearer ${this.token}`, "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body), signal,
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
    return data as T;
  }

  createTask(task: TaskInput) { return this.request<Snapshot>("/tasks", task); }
  snapshot(id: string) { return this.request<Snapshot>(`/tasks/${id}`); }
  message(id: string, message: string) { return this.request<Snapshot>(`/tasks/${id}/messages`, { message }); }
  cancel(id: string) { return this.request<Snapshot>(`/tasks/${id}/cancel`, {}); }
  approve(id: string, approval_id: string, approved: boolean) {
    return this.request<Snapshot>(`/tasks/${id}/approvals`, { approval_id, approved });
  }
  answerComputer(id: string, request_id: string, result: ComputerResult) {
    return this.request<Snapshot>(`/tasks/${id}/computer/results`, { request_id, result });
  }
  review(id: string, corrected_plan: Plan, feedback: string, consent_for_training = false) {
    return this.request<Snapshot>(`/tasks/${id}/reviews`, { corrected_plan, feedback, consent_for_training });
  }
  // Cursor-based long polling is easier to reconnect than a custom SSE parser.
  // Native execution MUST deduplicate request ids and consult the latest snapshot
  // before responding after reconnect; replayed events are not new authorizations.
  async *events(id: string, after = 0, signal?: AbortSignal): AsyncGenerator<Event> {
    let cursor = after;
    while (!signal?.aborted) {
      const batch = await this.request<{ events: Event[]; cursor: number }>(
        `/tasks/${id}/events?after=${cursor}&wait=20`, undefined, signal);
      for (const event of batch.events) { cursor = event.seq; yield event; }
      cursor = Math.max(cursor, batch.cursor);
      if (batch.events.some(e => e.type === "task.status" &&
          ["completed", "handoff", "cancelled", "failed", "deadline_stopped"].includes(String(e.data.status)))) return;
    }
  }
}
