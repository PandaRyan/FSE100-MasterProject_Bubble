// src/api/bubbleApi.ts
// REST client and localStorage high-score manager for Bubble Blitz.
// Matches the Draft API Contract and connects to bubble_router.py.

// ---- Constants (with sources from project requirements & Draft API Contract) ----
export const DEFAULT_API_BASE_URL = "http://localhost:8000"; // Default FastAPI port in main.py and FingerCounting.tsx
export const API_BASE_URL: string =
  (import.meta.env.VITE_API_URL as string | undefined) ?? DEFAULT_API_BASE_URL; // Env override for free-host deployment

export const LEVEL_EASY = 1; // Draft API Contract: level 1 = easy
export const LEVEL_MEDIUM = 2; // Draft API Contract: level 2 = medium
export const LEVEL_HARD = 3; // Draft API Contract: level 3 = hard

export const MAX_BATCH_EVENTS = 100; // Draft API Contract: at most 100 events per batch
export const MS_PER_SECOND = 1000; // Conversion factor from performance.now() ms to backend seconds
export const HTTP_NOT_FOUND = 404; // Draft API Contract: 404 unknown game means "offer a fresh start"
export const HTTP_SERVICE_UNAVAILABLE = 503; // Draft API Contract: 503 means the server is busy

const HIGH_SCORE_STORAGE_KEY = "bubble_blitz_high_scores"; // Single localStorage key for per-level best score & stars
const INITIAL_HIGH_SCORE = 0; // Default score/stars before a child completes a level

// ---- TypeScript Interfaces ----

export type LevelId = 1 | 2 | 3;
export type BubbleType = "plain" | "drag" | "pinch";

export type ClientEventType =
  | "tap"
  | "drag_start"
  | "drag_move"
  | "drag_end"
  | "pinch_start"
  | "pinch_move"
  | "pinch_end";

export interface ClientInputEvent {
  type: ClientEventType;
  t: number; // Raw client timestamp in seconds
  x?: number;
  y?: number;
  x1?: number;
  y1?: number;
  x2?: number;
  y2?: number;
}

export interface BubbleDTO {
  id: number;
  x: number;
  y: number;
  radius: number;
  type: BubbleType;
  taps_needed: number;
  taps_done: number;
  is_held: boolean;
  seconds_of_life_left: number;
}

export interface GameResultsDTO {
  won: boolean;
  score: number;
  stars: number;
  strikes: number;
  popped_count: number;
}

export interface ServerGameEventDTO {
  id: number;
  type: "popped" | "expired" | "strike" | "tap_progress" | "released" | "level_end";
  game_time: number;
  bubble_id?: number;
  x?: number;
  y?: number;
  radius?: number;
  bubble_type?: BubbleType;
  points_earned?: number;
  taps_done?: number;
  taps_needed?: number;
  strikes?: number;
  reason?: string;
  results?: GameResultsDTO;
}

export interface IgnoredInputDTO {
  type: string;
  t: number;
  reason: string;
}

export interface GameStateResponse {
  game_id: string;
  level: LevelId;
  game_time: number;
  seconds_left: number;
  score: number;
  strikes: number;
  finished: boolean;
  results: GameResultsDTO | null;
  bubbles: BubbleDTO[];
  events: ServerGameEventDTO[];
  ignored: IgnoredInputDTO[];
}

export class ApiError extends Error {
  status: number;
  code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

export interface LevelHighScore {
  bestScore: number;
  bestStars: number;
}

type HighScoreMap = Record<LevelId, LevelHighScore>;

// ---- Time Helper ----

/**
 * Returns the current client monotonic clock in seconds.
 * Using performance.now() guarantees the client clock never jumps backwards if the system clock adjusts.
 */
export function getClientTimeSeconds(): number {
  return performance.now() / MS_PER_SECOND;
}

// ---- API Functions ----

/**
 * Calls GET /health on app or page load to wake a sleeping free host before the child presses play.
 * Swallows network errors so a waking server does not crash the UI.
 */
export async function wakeServerHealth(): Promise<boolean> {
  try {
    const response = await fetch(`${API_BASE_URL}/health`, { method: "GET" });
    return response.ok;
  } catch {
    return false;
  }
}

/**
 * Helper to parse either a valid JSON response or throw a typed ApiError with HTTP status and code.
 */
async function parseResponseOrThrow<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let code = "HTTP_ERROR";
    let message = `Request failed with status ${response.status}`;
    try {
      const errBody = (await response.json()) as { code?: string; message?: string };
      if (errBody.code) code = errBody.code;
      if (errBody.message) message = errBody.message;
    } catch {
      // Fallback if response body was not JSON
    }
    throw new ApiError(response.status, code, message);
  }
  return (await response.json()) as T;
}

/**
 * Creates and starts a new game session on the server.
 */
export async function createGameSession(
  level: LevelId,
  startTimeSeconds: number,
  seed?: number
): Promise<GameStateResponse> {
  const response = await fetch(`${API_BASE_URL}/api/games`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      level,
      seed: seed ?? null,
      start_time: startTimeSeconds,
    }),
  });
  return parseResponseOrThrow<GameStateResponse>(response);
}

/**
 * Sends a batch of timestamped input events (up to 100) and receives the updated game state.
 */
export async function sendEventBatch(
  gameId: string,
  clientTimeSeconds: number,
  lastEventId: number,
  events: ClientInputEvent[]
): Promise<GameStateResponse> {
  const cappedEvents = events.slice(0, MAX_BATCH_EVENTS);
  const response = await fetch(`${API_BASE_URL}/api/games/${encodeURIComponent(gameId)}/events`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      client_time: clientTimeSeconds,
      last_event_id: lastEventId,
      events: cappedEvents,
    }),
  });
  return parseResponseOrThrow<GameStateResponse>(response);
}

// ---- High Score Functions (Frontend localStorage only, no personal data) ----

function createEmptyHighScoreMap(): HighScoreMap {
  return {
    [LEVEL_EASY]: { bestScore: INITIAL_HIGH_SCORE, bestStars: INITIAL_HIGH_SCORE },
    [LEVEL_MEDIUM]: { bestScore: INITIAL_HIGH_SCORE, bestStars: INITIAL_HIGH_SCORE },
    [LEVEL_HARD]: { bestScore: INITIAL_HIGH_SCORE, bestStars: INITIAL_HIGH_SCORE },
  };
}

/**
 * Reads all high scores from localStorage safely without throwing if storage is empty or blocked.
 */
export function getAllHighScores(): HighScoreMap {
  const defaults = createEmptyHighScoreMap();
  try {
    const raw = window.localStorage.getItem(HIGH_SCORE_STORAGE_KEY);
    if (!raw) return defaults;
    const parsed = JSON.parse(raw) as Partial<Record<LevelId, Partial<LevelHighScore>>>;
    for (const lvl of [LEVEL_EASY, LEVEL_MEDIUM, LEVEL_HARD] as const) {
      const entry = parsed[lvl];
      if (entry) {
        defaults[lvl] = {
          bestScore: typeof entry.bestScore === "number" ? entry.bestScore : INITIAL_HIGH_SCORE,
          bestStars: typeof entry.bestStars === "number" ? entry.bestStars : INITIAL_HIGH_SCORE,
        };
      }
    }
    return defaults;
  } catch {
    return defaults;
  }
}

/**
 * Gets the stored high score and best star count for a single level.
 */
export function getLevelHighScore(level: LevelId): LevelHighScore {
  return getAllHighScores()[level];
}

/**
 * Updates a level's best score and best stars in localStorage if the new result is higher.
 * Returns the updated LevelHighScore.
 */
export function recordLevelHighScore(
  level: LevelId,
  score: number,
  stars: number
): LevelHighScore {
  const all = getAllHighScores();
  const current = all[level];
  const updated: LevelHighScore = {
    bestScore: Math.max(current.bestScore, score),
    bestStars: Math.max(current.bestStars, stars),
  };
  all[level] = updated;
  try {
    window.localStorage.setItem(HIGH_SCORE_STORAGE_KEY, JSON.stringify(all));
  } catch {
    // Ignore storage quota errors so the game cannot crash
  }
  return updated;
}