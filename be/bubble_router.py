# bubble_router.py
# FastAPI REST router connecting EasyBubbleGame, MediumBubbleGame, and HardBubbleGame
# to the React frontend per the Draft API Contract.

import random
import time
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from easybubble import EasyBubbleGame
from mediumbubble import MediumBubbleGame
from hardbubble import HardBubbleGame

# ---- Constants (with sources from requirements & Draft API Contract) ----
LEVEL_EASY = 1                      # Draft API Contract: level 1 = easy
LEVEL_MEDIUM = 2                    # Draft API Contract: level 2 = medium
LEVEL_HARD = 3                      # Draft API Contract: level 3 = hard

CANVAS_WIDTH = 1920                 # Project requirement: fixed virtual canvas width in px
CANVAS_HEIGHT = 1080                # Project requirement: fixed virtual canvas height in px

PAUSE_GAP_THRESHOLD = 0.75          # Draft API Contract: gap > 0.75 s between events is treated as a pause
MAX_BATCH_EVENTS = 100              # Draft API Contract: at most 100 events per batch
IDLE_TIMEOUT_SECONDS = 600.0        # Draft API Contract: idle games deleted after 10 minutes (10 * 60 s)
FINISHED_TIMEOUT_SECONDS = 120.0    # Draft API Contract: finished games deleted after 2 minutes (2 * 60 s)
MAX_ACTIVE_GAMES = 500              # Free-host safety cap to prevent memory exhaustion; triggers 503 when full

FIRST_EVENT_ID = 1                  # Draft API Contract: events are numbered starting from 1
DEFAULT_TAPS_NEEDED = 1             # Easy and Hard bubbles pop in 1 tap
DEFAULT_TAPS_DONE = 0               # Easy and Hard bubbles have 0 prior taps before popping
MIN_TIME_LEFT = 0.0                 # Clamp seconds_left so it does not display a negative number
INITIAL_PAUSED_TIME = 0.0           # Starting accumulated pause offset in seconds
ROUND_TIME_DIGITS = 4               # Decimal places for rounding game_time in JSON responses
ROUND_LIFE_DIGITS = 3               # Decimal places for rounding seconds_left and seconds_of_life_left
ROUND_COORD_DIGITS = 2              # Decimal places for rounding bubble x and y coordinates

router = APIRouter(prefix="/api/games", tags=["bubble_blitz"])


# ---- Pydantic Models (like typed Python dataclasses for JSON validation) ----

class CreateGameRequest(BaseModel):
    level: int
    seed: Optional[int] = None
    start_time: float


class ClientInputEvent(BaseModel):
    type: str                       # "tap", "drag_start", "drag_move", "drag_end", "pinch_start", "pinch_move", "pinch_end"
    t: float                        # Raw client timestamp in seconds
    x: Optional[float] = None
    y: Optional[float] = None
    x1: Optional[float] = None
    y1: Optional[float] = None
    x2: Optional[float] = None
    y2: Optional[float] = None


class BatchEventsRequest(BaseModel):
    client_time: float
    last_event_id: int = 0
    events: List[ClientInputEvent] = []


# ---- In-Memory Session Wrapper ----

class GameSession:
    def __init__(self, game_id: str, level: int, game_obj: Any, raw_start_time: float):
        self.game_id = game_id
        self.level = level
        self.game = game_obj
        self.last_raw_time = raw_start_time
        self.total_paused_time = INITIAL_PAUSED_TIME
        self.last_game_time = raw_start_time
        self.next_event_id = FIRST_EVENT_ID
        self.event_log: List[Dict[str, Any]] = []
        self.updated_wall_time = time.monotonic()
        self.finished_wall_time: Optional[float] = None

    def to_game_time(self, raw_time: float) -> float:
        """Clamps backwards timestamps and freezes game time across pause gaps (> 0.75 s)."""
        clamped = max(raw_time, self.last_raw_time)
        delta = clamped - self.last_raw_time
        if delta > PAUSE_GAP_THRESHOLD:
            self.total_paused_time += delta
        self.last_raw_time = clamped
        self.last_game_time = clamped - self.total_paused_time
        return self.last_game_time

    def append_event(self, event_type: str, game_time: float, **payload: Any) -> None:
        evt: Dict[str, Any] = {
            "id": self.next_event_id,
            "type": event_type,
            "game_time": round(game_time, ROUND_TIME_DIGITS),
        }
        evt.update(payload)
        self.event_log.append(evt)
        self.next_event_id += 1


# Active game store in memory (no personal data stored per project rules)
SESSIONS: Dict[str, GameSession] = {}


def _cleanup_expired_sessions() -> None:
    """Deletes idle games after 10 minutes and finished games after 2 minutes."""
    now = time.monotonic()
    to_delete = []
    for gid, session in SESSIONS.items():
        if session.finished_wall_time is not None:
            if now - session.finished_wall_time >= FINISHED_TIMEOUT_SECONDS:
                to_delete.append(gid)
        elif now - session.updated_wall_time >= IDLE_TIMEOUT_SECONDS:
            to_delete.append(gid)
    for gid in to_delete:
        del SESSIONS[gid]


def _error_response(status_code: int, code: str, message: str) -> JSONResponse:
    """Formats errors with a real HTTP status code and one JSON body (code + message)."""
    return JSONResponse(
        status_code=status_code,
        content={"code": code, "message": message},
    )


def _snapshot_bubbles(game: Any) -> Dict[int, Dict[str, Any]]:
    """Takes a lightweight snapshot of active bubbles before a step so we can diff events."""
    snap: Dict[int, Dict[str, Any]] = {}
    for b in game.get_active_bubbles():
        snap[b.bubble_id] = {
            "id": b.bubble_id,
            "x": b.x,
            "y": b.y,
            "radius": b.radius,
            "type": getattr(b, "bubble_type", "plain"),
            "taps_needed": getattr(b, "tap_count", DEFAULT_TAPS_NEEDED),
            "taps_done": getattr(b, "taps_done", DEFAULT_TAPS_DONE),
            "is_held": getattr(b, "is_held", False),
            "spawn_time": b.spawn_time,
        }
    return snap


def _run_update_with_diff(session: GameSession, game_time: float) -> None:
    """Runs game.update(game_time) and records expired, strike, and level_end events."""
    game = session.game
    if game.finished:
        return

    before_bubbles = _snapshot_bubbles(game)
    before_strikes = game.strikes
    was_finished = game.finished

    game.update(game_time)

    after_ids = {b.bubble_id for b in game.get_active_bubbles()}
    removed_ids = [bid for bid in before_bubbles if bid not in after_ids]

    # Any bubble removed during update() expired
    for bid in removed_ids:
        b_info = before_bubbles[bid]
        session.append_event(
            "expired",
            game_time,
            bubble_id=bid,
            x=b_info["x"],
            y=b_info["y"],
            radius=b_info["radius"],
        )

    strikes_added = game.strikes - before_strikes
    for _ in range(strikes_added):
        session.append_event(
            "strike",
            game_time,
            strikes=game.strikes,
            reason="expired",
        )

    if not was_finished and game.finished:
        if session.finished_wall_time is None:
            session.finished_wall_time = time.monotonic()
        session.append_event("level_end", game_time, results=game.get_results())


def _run_input_with_diff(
    session: GameSession,
    ev: ClientInputEvent,
    game_time: float,
    ignored_out: List[Dict[str, Any]],
) -> None:
    """Runs update(game_time) first, then the input handler, and diffs state to emit events."""
    game = session.game

    # Call update(game_time) before handling input at the same timestamp
    # so a bubble that expired on this frame cannot still be popped.
    _run_update_with_diff(session, game_time)

    if game.finished:
        ignored_out.append({"type": ev.type, "t": ev.t, "reason": "level_finished"})
        return

    before_bubbles = _snapshot_bubbles(game)
    before_score = game.score
    before_strikes = game.strikes
    was_finished = game.finished

    etype = ev.type
    if etype == "tap" and ev.x is not None and ev.y is not None:
        game.handle_tap(ev.x, ev.y, game_time)
    elif etype == "drag_start" and ev.x is not None and ev.y is not None:
        game.handle_drag_start(ev.x, ev.y, game_time)
    elif etype == "drag_move" and ev.x is not None and ev.y is not None:
        game.handle_drag_move(ev.x, ev.y, game_time)
    elif etype == "drag_end" and ev.x is not None and ev.y is not None:
        game.handle_drag_end(ev.x, ev.y, game_time)
    elif etype == "pinch_start" and None not in (ev.x1, ev.y1, ev.x2, ev.y2):
        game.handle_pinch_start(ev.x1, ev.y1, ev.x2, ev.y2, game_time)
    elif etype == "pinch_move" and None not in (ev.x1, ev.y1, ev.x2, ev.y2):
        game.handle_pinch_move(ev.x1, ev.y1, ev.x2, ev.y2, game_time)
    elif etype == "pinch_end" and None not in (ev.x1, ev.y1, ev.x2, ev.y2):
        game.handle_pinch_end(ev.x1, ev.y1, ev.x2, ev.y2, game_time)
    else:
        ignored_out.append({"type": etype, "t": ev.t, "reason": "invalid_event_fields"})
        return

    after_bubbles = _snapshot_bubbles(game)
    score_delta = game.score - before_score
    strikes_delta = game.strikes - before_strikes
    state_changed = False

    # 1. Check for popped bubbles (removed during an input call)
    for bid, b_before in before_bubbles.items():
        if bid not in after_bubbles:
            state_changed = True
            session.append_event(
                "popped",
                game_time,
                bubble_id=bid,
                x=b_before["x"],
                y=b_before["y"],
                radius=b_before["radius"],
                bubble_type=b_before["type"],
                points_earned=score_delta,
            )

    # 2. Check surviving bubbles for tap_progress, released, or gesture hold/movement
    for bid, b_after in after_bubbles.items():
        if bid in before_bubbles:
            b_before = before_bubbles[bid]
            if b_after["taps_done"] > b_before["taps_done"]:
                state_changed = True
                session.append_event(
                    "tap_progress",
                    game_time,
                    bubble_id=bid,
                    x=b_after["x"],
                    y=b_after["y"],
                    taps_done=b_after["taps_done"],
                    taps_needed=b_after["taps_needed"],
                )
            if b_before["is_held"] and not b_after["is_held"]:
                state_changed = True
                session.append_event(
                    "released",
                    game_time,
                    bubble_id=bid,
                    x=b_after["x"],
                    y=b_after["y"],
                )
            if (
                b_after["is_held"] != b_before["is_held"]
                or b_after["x"] != b_before["x"]
                or b_after["y"] != b_before["y"]
            ):
                state_changed = True

    # 3. Check for strikes from empty-space tap
    if strikes_delta > 0:
        state_changed = True
        for _ in range(strikes_delta):
            session.append_event(
                "strike",
                game_time,
                strikes=game.strikes,
                reason="empty_tap",
                x=ev.x,
                y=ev.y,
            )

    # 4. Check for level_end
    if not was_finished and game.finished:
        state_changed = True
        if session.finished_wall_time is None:
            session.finished_wall_time = time.monotonic()
        session.append_event("level_end", game_time, results=game.get_results())

    # 5. If nothing changed (e.g., tap on a drag/pinch bubble or gesture on empty space), mark ignored
    if not state_changed:
        ignored_out.append({"type": etype, "t": ev.t, "reason": "no_effect"})


def _serialize_bubbles(game: Any, current_game_time: float) -> List[Dict[str, Any]]:
    """Serializes active bubbles with exact fields required by the Draft API Contract."""
    out: List[Dict[str, Any]] = []
    for b in game.get_active_bubbles():
        age = max(MIN_TIME_LEFT, current_game_time - b.spawn_time)
        life_left = max(MIN_TIME_LEFT, b.lifetime - age)
        out.append({
            "id": b.bubble_id,
            "x": round(b.x, ROUND_COORD_DIGITS),
            "y": round(b.y, ROUND_COORD_DIGITS),
            "radius": b.radius,
            "type": getattr(b, "bubble_type", "plain"),
            "taps_needed": getattr(b, "tap_count", DEFAULT_TAPS_NEEDED),
            "taps_done": getattr(b, "taps_done", DEFAULT_TAPS_DONE),
            "is_held": getattr(b, "is_held", False),
            "seconds_of_life_left": round(life_left, ROUND_LIFE_DIGITS),
        })
    return out


def _build_state_response(
    session: GameSession,
    last_event_id: int,
    ignored: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Builds the standard response dictionary returned by both create and event batch calls."""
    game = session.game
    elapsed = max(MIN_TIME_LEFT, session.last_game_time - game.start_time)
    seconds_left = MIN_TIME_LEFT if game.finished else max(MIN_TIME_LEFT, game.level_duration - elapsed)
    new_events = [e for e in session.event_log if e["id"] > last_event_id]

    return {
        "game_id": session.game_id,
        "level": session.level,
        "game_time": round(session.last_game_time, ROUND_TIME_DIGITS),
        "seconds_left": round(seconds_left, ROUND_LIFE_DIGITS),
        "score": game.score,
        "strikes": game.strikes,
        "finished": game.finished,
        "results": game.get_results() if game.finished else None,
        "bubbles": _serialize_bubbles(game, session.last_game_time),
        "events": new_events,
        "ignored": ignored,
    }


# ---- REST Endpoints ----

@router.post("")
async def create_game(req: CreateGameRequest):
    _cleanup_expired_sessions()

    if len(SESSIONS) >= MAX_ACTIVE_GAMES:
        return _error_response(503, "SERVER_BUSY", "Server is busy; please try again shortly.")

    rng = random.Random(req.seed) if req.seed is not None else random.Random()

    if req.level == LEVEL_EASY:
        game = EasyBubbleGame(width=CANVAS_WIDTH, height=CANVAS_HEIGHT, rng=rng)
    elif req.level == LEVEL_MEDIUM:
        game = MediumBubbleGame(width=CANVAS_WIDTH, height=CANVAS_HEIGHT, rng=rng)
    elif req.level == LEVEL_HARD:
        game = HardBubbleGame(width=CANVAS_WIDTH, height=CANVAS_HEIGHT, rng=rng)
    else:
        return _error_response(400, "INVALID_LEVEL", "Level must be 1 (easy), 2 (medium), or 3 (hard).")

    game.start(req.start_time)
    game_id = str(uuid.uuid4())
    session = GameSession(game_id=game_id, level=req.level, game_obj=game, raw_start_time=req.start_time)
    SESSIONS[game_id] = session

    return _build_state_response(session, last_event_id=0, ignored=[])


@router.post("/{game_id}/events")
async def process_event_batch(game_id: str, req: BatchEventsRequest):
    _cleanup_expired_sessions()

    session = SESSIONS.get(game_id)
    if session is None:
        return _error_response(404, "GAME_NOT_FOUND", "Game not found or expired; offer a fresh start.")

    if len(req.events) > MAX_BATCH_EVENTS:
        return _error_response(400, "BATCH_TOO_LARGE", f"At most {MAX_BATCH_EVENTS} events per batch.")

    session.updated_wall_time = time.monotonic()
    ignored: List[Dict[str, Any]] = []

    # Input after the level ends returns a normal response with the final state and results
    if session.game.finished:
        for ev in req.events:
            ignored.append({"type": ev.type, "t": ev.t, "reason": "level_finished"})
        return _build_state_response(session, last_event_id=req.last_event_id, ignored=ignored)

    # Sort events chronologically by raw timestamp as required by the Draft API Contract
    sorted_events = sorted(req.events, key=lambda e: e.t)

    for ev in sorted_events:
        t_game = session.to_game_time(ev.t)
        _run_input_with_diff(session, ev, t_game, ignored)
        if session.game.finished:
            break

    # Advance the game to the batch's overall client_time if the level is still running
    if not session.game.finished:
        t_batch = session.to_game_time(req.client_time)
        _run_update_with_diff(session, t_batch)

    return _build_state_response(session, last_event_id=req.last_event_id, ignored=ignored)