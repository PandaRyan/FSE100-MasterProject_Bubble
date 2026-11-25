// src/components/BubbleBlitzBoard.tsx
// Shared 1920x1080 letterboxed game board, HUD, gesture tracker, and 100ms REST loop
// used by BubbleBlitzEasy, BubbleBlitzMedium, and BubbleBlitzHard.

import React, { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  ApiError,
  createGameSession,
  getClientTimeSeconds,
  getLevelHighScore,
  HTTP_NOT_FOUND,
  HTTP_SERVICE_UNAVAILABLE,
  LEVEL_HARD,
  LEVEL_MEDIUM,
  MAX_BATCH_EVENTS,
  recordLevelHighScore,
  sendEventBatch,
  wakeServerHealth,
} from "../api/bubbleApi";
import type {
  BubbleDTO,
  ClientInputEvent,
  GameResultsDTO,
  GameStateResponse,
  LevelHighScore,
  LevelId,
  ServerGameEventDTO,
} from "../api/bubbleApi";

import background from "../assets/background.jpg";
import backImg from "../assets/back.png";
import plainBubbleImg from "../assets/bubble.png";
import moveBubbleImg from "../assets/movebubble.png";
import pinchBubbleImg from "../assets/pinchbubble.jpg";
import spikesImg from "../assets/spikes.png";
import "./bubbleblitz.css";

// ---- Constants (with sources from project rules & backend files) ----
const VIRTUAL_WIDTH = 1920; // Project rule: fixed virtual canvas width in px
const VIRTUAL_HEIGHT = 1080; // Project rule: fixed virtual canvas height in px
const TOP_BAND_HEIGHT = 120; // Backend TOP_BAND = 120 px reserved for HUD (strikes, timer, score)
const SPIKE_STRIP_WIDTH = 100; // Backend SPIKE_STRIP = 100 px on each side in Hard mode

const TAP_MOVE_LIMIT_PX = 20; // Frontend rule: finger moving <= 20 px on lift is a tap; > 20 px is a gesture
const TAP_MOVE_LIMIT_SQ = TAP_MOVE_LIMIT_PX * TAP_MOVE_LIMIT_PX; // 20^2 = 400 px^2 to avoid sqrt when checking distance

const BATCH_INTERVAL_MS = 100; // Draft API Contract: send event batch at least every 100 ms
const EFFECT_DURATION_MS = 500; // Visual pop/expiry/strike effect lifetime (under the 1s output requirement)
const MAX_STRIKES = 3; // Project rule: 3 X's (strikes) = lose
const MAX_STARS = 3; // Project rule: 1 to 3 stars on win, 0 on loss
const STRIKE_SLOTS = [1, 2, 3] as const; // 3 strike X indicators in the HUD
const STAR_SLOTS = [1, 2, 3] as const; // 3 star indicators on the results screen

const INITIAL_SCALE = 1; // Default scale factor before first window measurement
const INITIAL_EVENT_ID = 0; // Draft API Contract: events start at 1, so 0 means none received yet
const INITIAL_SCORE = 0; // Starting score at level start
const INITIAL_STRIKES = 0; // Starting strikes at level start
const EMPTY_COUNT = 0; // Zero count check for arrays, maps, and bounds
const MIN_POSITIVE_POINTS = 0; // Threshold to check if points_earned > 0
const MIN_TAPS_REMAINING = 1; // Floor for remaining taps badge on an active Medium bubble
const SINGLE_TOUCH_COUNT = 1; // 1 active pointer = tap or drag candidate
const PINCH_TOUCH_COUNT = 2; // 2 active pointers = pinch gesture
const DIAMETER_MULTIPLIER = 2; // Bubble width and height equal 2 * radius
const MIRROR_FACTOR = 2; // Reflection formula x2 = 2 * center - x1 for Shift+Drag pinch testing

const getIntroCopy = (level: LevelId) => {
  if (level === LEVEL_HARD) {
    return {
      popTitle: "How to Pop Bubbles",
      popText:
        "Tap plain bubbles, drag DRAG bubbles into the side spikes, and use two fingers to pinch PINCH bubbles!",
      strikesTitle: "Watch Out for X's!",
      strikesText:
        "Letting any bubble expire or tapping empty space gives you an X. Get 3 X's and you lose—survive the timer to win!",
    };
  }
  if (level === LEVEL_MEDIUM) {
    return {
      popTitle: "How to Pop Bubbles",
      popText:
        "Each bubble has a number on it. Tap the bubble that many times until the number hits 0 to pop it!",
      strikesTitle: "Watch Out for X's!",
      strikesText:
        "If a bubble disappears before you pop it, or if you tap empty space, you get an X. 3 X's and it's game over!",
    };
  }
  return {
    popTitle: "How to Pop Bubbles",
    popText: "Tap each bubble once to pop it before it disappears!",
    strikesTitle: "Watch Out for X's!",
    strikesText:
      "Missing a bubble or tapping empty space gives you an X. Get 3 X's and the game ends—survive until the timer hits 0 to win!",
  };
};

export interface BubbleBlitzBoardProps {
  level: LevelId;
  modeTitle: string;
  modeBannerImg: string;
  initialSeconds: number;
}

interface ActivePointer {
  pointerId: number;
  startX: number;
  startY: number;
  currentX: number;
  currentY: number;
}

type PointerMap = Map<number, ActivePointer>;

interface VisualEffect {
  key: string;
  type: "popped" | "expired" | "strike" | "released";
  x: number;
  y: number;
  text?: string;
}

const BubbleBlitzBoard: React.FC<BubbleBlitzBoardProps> = ({
  level,
  modeTitle,
  modeBannerImg,
  initialSeconds,
}) => {
  const navigate = useNavigate();

  // ---- React State for Rendering ----
  const [scale, setScale] = useState<number>(INITIAL_SCALE);
  const [bubbles, setBubbles] = useState<BubbleDTO[]>([]);
  const [score, setScore] = useState<number>(INITIAL_SCORE);
  const [strikes, setStrikes] = useState<number>(INITIAL_STRIKES);
  const [secondsLeft, setSecondsLeft] = useState<number>(initialSeconds);
  const [finished, setFinished] = useState<boolean>(false);
  const [results, setResults] = useState<GameResultsDTO | null>(null);
  const [highScore, setHighScore] = useState<LevelHighScore>(() => getLevelHighScore(level));
  const [effects, setEffects] = useState<VisualEffect[]>([]);
  const [introStep, setIntroStep] = useState<1 | 2 | null>(1);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [errorModal, setErrorModal] = useState<{ title: string; message: string } | null>(null);

  // ---- Mutable Refs for Real-Time Loop & Gestures (no re-render lag) ----
  const stageRef = useRef<HTMLDivElement | null>(null);
  const gameIdRef = useRef<string | null>(null);
  const finishedRef = useRef<boolean>(false);
  const lastEventIdRef = useRef<number>(INITIAL_EVENT_ID);
  const pendingEventsRef = useRef<ClientInputEvent[]>([]);
  const inFlightRef = useRef<boolean>(false);
  const bubblesRef = useRef<BubbleDTO[]>([]);

  // Pointer & gesture state machine refs
  const pointersRef = useRef<PointerMap>(new Map());
  const gestureModeRef = useRef<"none" | "tap_candidate" | "dragging" | "pinching">("none");
  const shiftMirrorCenterRef = useRef<{ x: number; y: number } | null>(null);

  // ---- Window Letterbox Scale Calculation (1920x1080) ----
  useEffect(() => {
    const updateScale = () => {
      const scaleX = window.innerWidth / VIRTUAL_WIDTH;
      const scaleY = window.innerHeight / VIRTUAL_HEIGHT;
      setScale(Math.min(scaleX, scaleY));
    };
    updateScale();
    window.addEventListener("resize", updateScale);
    return () => window.removeEventListener("resize", updateScale);
  }, []);

  // ---- Helper: Spawn Brief Floating Animation Effect ----
  const triggerVisualEffects = useCallback((serverEvents: ServerGameEventDTO[]) => {
    if (serverEvents.length === EMPTY_COUNT) return;
    const added: VisualEffect[] = [];

    for (const ev of serverEvents) {
      if (ev.type === "popped" && ev.x !== undefined && ev.y !== undefined) {
        const pts =
          ev.points_earned && ev.points_earned > MIN_POSITIVE_POINTS
            ? `+${ev.points_earned}`
            : "POP!";
        added.push({
          key: `evt-${ev.id}`,
          type: "popped",
          x: ev.x,
          y: ev.y,
          text: pts,
        });
      } else if (ev.type === "expired" && ev.x !== undefined && ev.y !== undefined) {
        added.push({
          key: `evt-${ev.id}`,
          type: "expired",
          x: ev.x,
          y: ev.y,
          text: "MISS!",
        });
      } else if (ev.type === "strike" && ev.x !== undefined && ev.y !== undefined) {
        added.push({
          key: `evt-${ev.id}`,
          type: "strike",
          x: ev.x,
          y: ev.y,
          text: "X",
        });
      } else if (ev.type === "released" && ev.x !== undefined && ev.y !== undefined) {
        added.push({
          key: `evt-${ev.id}`,
          type: "released",
          x: ev.x,
          y: ev.y,
          text: "RESET",
        });
      }
    }

    if (added.length > EMPTY_COUNT) {
      setEffects((prev) => [...prev, ...added]);
      window.setTimeout(() => {
        const keysToRemove = new Set(added.map((a) => a.key));
        setEffects((prev) => prev.filter((item) => !keysToRemove.has(item.key)));
      }, EFFECT_DURATION_MS);
    }
  }, []);

  // ---- Apply Server Response to Board State ----
  const applyServerState = useCallback(
    (state: GameStateResponse) => {
      bubblesRef.current = state.bubbles;
      setBubbles(state.bubbles);
      setScore(state.score);
      setStrikes(state.strikes);
      setSecondsLeft(state.seconds_left);

      if (state.events.length > EMPTY_COUNT) {
        const maxId = state.events[state.events.length - SINGLE_TOUCH_COUNT].id;
        if (maxId > lastEventIdRef.current) {
          lastEventIdRef.current = maxId;
        }
        triggerVisualEffects(state.events);
      }

      if (state.finished) {
        finishedRef.current = true;
        setFinished(true);
        if (state.results) {
          setResults(state.results);
          const updatedBest = recordLevelHighScore(
            level,
            state.results.score,
            state.results.stars
          );
          setHighScore(updatedBest);
        }
      }
    },
    [level, triggerVisualEffects]
  );

  // ---- Flush Event Batch to Backend ----
  const flushBatch = useCallback(
    async (isImmediateTapFlush: boolean) => {
      const gameId = gameIdRef.current;
      if (!gameId || finishedRef.current) return;

      // Draft API Contract: only one batch in flight at a time, except an immediate tap flush
      if (inFlightRef.current && !isImmediateTapFlush) {
        return;
      }

      const eventsToSend = pendingEventsRef.current.splice(EMPTY_COUNT, MAX_BATCH_EVENTS);
      const clientTime = getClientTimeSeconds();

      inFlightRef.current = true;
      try {
        const state = await sendEventBatch(
          gameId,
          clientTime,
          lastEventIdRef.current,
          eventsToSend
        );
        applyServerState(state);
      } catch (err) {
        if (err instanceof ApiError) {
          if (err.status === HTTP_NOT_FOUND) {
            finishedRef.current = true;
            setErrorModal({
              title: "Game Timed Out",
              message: "This session expired after inactivity. Let's start a fresh game!",
            });
          } else if (err.status === HTTP_SERVICE_UNAVAILABLE) {
            setErrorModal({
              title: "Server Busy",
              message: "The game server is a little busy right now. Tap below to try again!",
            });
          }
        }
      } finally {
        inFlightRef.current = false;
      }
    },
    [applyServerState]
  );

  // ---- Start or Restart Level ----
  const startNewLevel = useCallback(async () => {
    setErrorModal(null);
    setStatusMessage("Getting bubbles ready...");
    finishedRef.current = false;
    setFinished(false);
    setResults(null);
    setBubbles([]);
    bubblesRef.current = [];
    setScore(INITIAL_SCORE);
    setStrikes(INITIAL_STRIKES);
    setSecondsLeft(initialSeconds);
    lastEventIdRef.current = INITIAL_EVENT_ID;
    pendingEventsRef.current = [];
    pointersRef.current.clear();
    gestureModeRef.current = "none";
    shiftMirrorCenterRef.current = null;

    try {
      await wakeServerHealth();
      const startTime = getClientTimeSeconds();
      const initialState = await createGameSession(level, startTime);
      gameIdRef.current = initialState.game_id;
      setStatusMessage(null);
      applyServerState(initialState);
    } catch (err) {
      setStatusMessage(null);
      if (err instanceof ApiError && err.status === HTTP_SERVICE_UNAVAILABLE) {
        setErrorModal({
          title: "Server Busy",
          message: "The server is warming up or busy. Tap Start Fresh to play!",
        });
      } else {
        setErrorModal({
          title: "Connection Needed",
          message: "Could not reach the game server on port 8000. Make sure FastAPI is running!",
        });
      }
    }
  }, [applyServerState, initialSeconds, level]);

  // Wait to start the level and 100ms batch timer until the player finishes the 2-step intro
  useEffect(() => {
    if (introStep !== null) return;

    void startNewLevel();

    const intervalId = window.setInterval(() => {
      void flushBatch(false);
    }, BATCH_INTERVAL_MS);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [introStep, startNewLevel, flushBatch]);

  // ---- Coordinate Scaling: Screen (clientX, clientY) -> Virtual (0..1920, 0..1080) ----
  const toVirtualCoords = (clientX: number, clientY: number): { x: number; y: number } | null => {
    const stage = stageRef.current;
    if (!stage) return null;
    const rect = stage.getBoundingClientRect();
    if (rect.width <= EMPTY_COUNT || rect.height <= EMPTY_COUNT) return null;

    const x = (clientX - rect.left) * (VIRTUAL_WIDTH / rect.width);
    const y = (clientY - rect.top) * (VIRTUAL_HEIGHT / rect.height);

    // Ignore taps or gestures that land outside the 1920x1080 virtual canvas (letterbox bars)
    if (x < EMPTY_COUNT || x > VIRTUAL_WIDTH || y < EMPTY_COUNT || y > VIRTUAL_HEIGHT) {
      return null;
    }
    return { x, y };
  };

  const queueEvent = (evt: ClientInputEvent, immediateFlush = false) => {
    if (pendingEventsRef.current.length < MAX_BATCH_EVENTS) {
      pendingEventsRef.current.push(evt);
    }
    if (immediateFlush) {
      void flushBatch(true);
    }
  };

  // ---- Pointer Event Handlers (Tap <= 20px, Drag > 20px, Two-Finger or Shift Pinch) ----
  const handlePointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    if (finishedRef.current || introStep !== null || statusMessage || errorModal) return;

    const coords = toVirtualCoords(e.clientX, e.clientY);
    if (!coords) return;

    // Ignore clicks in the top 120 px HUD bar so tapping the Back button does not count as an empty-space strike
    if (coords.y < TOP_BAND_HEIGHT) return;

    e.currentTarget.setPointerCapture(e.pointerId);
    const t = getClientTimeSeconds();

    pointersRef.current.set(e.pointerId, {
      pointerId: e.pointerId,
      startX: coords.x,
      startY: coords.y,
      currentX: coords.x,
      currentY: coords.y,
    });

    const activeList = Array.from(pointersRef.current.values());

    // Desktop testing helper: holding Shift with 1 mouse pointer on Hard mode simulates a 2-finger pinch
    // by mirroring a second finger across the pinch bubble's center.
    if (level === LEVEL_HARD && e.shiftKey && activeList.length === SINGLE_TOUCH_COUNT) {
      const pinchTarget = bubblesRef.current.find((b) => b.type === "pinch");
      if (pinchTarget) {
        shiftMirrorCenterRef.current = { x: pinchTarget.x, y: pinchTarget.y };
        const x2 = MIRROR_FACTOR * pinchTarget.x - coords.x;
        const y2 = MIRROR_FACTOR * pinchTarget.y - coords.y;
        gestureModeRef.current = "pinching";
        queueEvent({
          type: "pinch_start",
          t,
          x1: coords.x,
          y1: coords.y,
          x2,
          y2,
        });
        return;
      }
    }

    if (activeList.length === SINGLE_TOUCH_COUNT) {
      gestureModeRef.current = "tap_candidate";
    } else if (activeList.length === PINCH_TOUCH_COUNT) {
      // If Finger 1 had already started dragging before Finger 2 landed, end that drag cleanly
      if (gestureModeRef.current === "dragging") {
        queueEvent({
          type: "drag_end",
          t,
          x: activeList[EMPTY_COUNT].currentX,
          y: activeList[EMPTY_COUNT].currentY,
        });
      }
      gestureModeRef.current = "pinching";
      const [p1, p2] = activeList;
      queueEvent({
        type: "pinch_start",
        t,
        x1: p1.currentX,
        y1: p1.currentY,
        x2: p2.currentX,
        y2: p2.currentY,
      });
    }
  };

  const handlePointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (finishedRef.current) return;
    const ptr = pointersRef.current.get(e.pointerId);
    if (!ptr) return;

    const coords = toVirtualCoords(e.clientX, e.clientY);
    if (!coords) return;

    ptr.currentX = coords.x;
    ptr.currentY = coords.y;
    const t = getClientTimeSeconds();

    // Check desktop Shift-mirror pinch first
    if (gestureModeRef.current === "pinching" && shiftMirrorCenterRef.current) {
      const center = shiftMirrorCenterRef.current;
      const x2 = MIRROR_FACTOR * center.x - coords.x;
      const y2 = MIRROR_FACTOR * center.y - coords.y;
      queueEvent({
        type: "pinch_move",
        t,
        x1: coords.x,
        y1: coords.y,
        x2,
        y2,
      });
      return;
    }

    const activeList = Array.from(pointersRef.current.values());

    if (gestureModeRef.current === "tap_candidate" && activeList.length === SINGLE_TOUCH_COUNT) {
      const dx = ptr.currentX - ptr.startX;
      const dy = ptr.currentY - ptr.startY;
      // Rule: Once a finger moves more than 20 px, send gesture events instead of a tap
      if (dx * dx + dy * dy > TAP_MOVE_LIMIT_SQ) {
        gestureModeRef.current = "dragging";
        // Drag start carries where the finger first landed
        queueEvent({
          type: "drag_start",
          t,
          x: ptr.startX,
          y: ptr.startY,
        });
        queueEvent({
          type: "drag_move",
          t,
          x: ptr.currentX,
          y: ptr.currentY,
        });
      }
    } else if (gestureModeRef.current === "dragging" && activeList.length === SINGLE_TOUCH_COUNT) {
      queueEvent({
        type: "drag_move",
        t,
        x: ptr.currentX,
        y: ptr.currentY,
      });
    } else if (gestureModeRef.current === "pinching" && activeList.length >= PINCH_TOUCH_COUNT) {
      const [p1, p2] = activeList;
      queueEvent({
        type: "pinch_move",
        t,
        x1: p1.currentX,
        y1: p1.currentY,
        x2: p2.currentX,
        y2: p2.currentY,
      });
    }
  };

  const handlePointerUpOrCancel = (e: React.PointerEvent<HTMLDivElement>) => {
    const ptr = pointersRef.current.get(e.pointerId);
    if (!ptr) return;

    const coords = toVirtualCoords(e.clientX, e.clientY);
    if (coords) {
      ptr.currentX = coords.x;
      ptr.currentY = coords.y;
    }

    const t = getClientTimeSeconds();
    const activeList = Array.from(pointersRef.current.values());

    if (gestureModeRef.current === "tap_candidate" && activeList.length === SINGLE_TOUCH_COUNT) {
      // Finger lifted within 20 px of where it landed -> send tap and flush batch immediately!
      queueEvent(
        {
          type: "tap",
          t,
          x: ptr.currentX,
          y: ptr.currentY,
        },
        true
      );
      gestureModeRef.current = "none";
    } else if (gestureModeRef.current === "dragging" && activeList.length === SINGLE_TOUCH_COUNT) {
      queueEvent({
        type: "drag_end",
        t,
        x: ptr.currentX,
        y: ptr.currentY,
      });
      gestureModeRef.current = "none";
    } else if (gestureModeRef.current === "pinching") {
      if (shiftMirrorCenterRef.current) {
        const center = shiftMirrorCenterRef.current;
        const x2 = MIRROR_FACTOR * center.x - ptr.currentX;
        const y2 = MIRROR_FACTOR * center.y - ptr.currentY;
        queueEvent({
          type: "pinch_end",
          t,
          x1: ptr.currentX,
          y1: ptr.currentY,
          x2,
          y2,
        });
        shiftMirrorCenterRef.current = null;
      } else if (activeList.length >= PINCH_TOUCH_COUNT) {
        const [p1, p2] = activeList;
        queueEvent({
          type: "pinch_end",
          t,
          x1: p1.currentX,
          y1: p1.currentY,
          x2: p2.currentX,
          y2: p2.currentY,
        });
      }
      gestureModeRef.current = "none";
    }

    pointersRef.current.delete(e.pointerId);
    if (pointersRef.current.size === EMPTY_COUNT) {
      gestureModeRef.current = "none";
      shiftMirrorCenterRef.current = null;
    }
  };

  // ---- Helper: Pick Bubble Image by Type ----
  const getBubbleImage = (b: BubbleDTO): string => {
    if (b.type === "drag") return moveBubbleImg;
    if (b.type === "pinch") return pinchBubbleImg;
    return plainBubbleImg;
  };

  const introCopy = getIntroCopy(level);

  return (
    <div className="bb-viewport">
      <img
        className="bb-background-video"
        src={background}
        alt="Game background"
      />

      {/* Fixed 1920x1080 Virtual Canvas scaled with letterbox bars */}
      <div
        ref={stageRef}
        className="bb-virtual-stage"
        style={{
          width: `${VIRTUAL_WIDTH}px`,
          height: `${VIRTUAL_HEIGHT}px`,
          transform: `translate(-50%, -50%) scale(${scale})`,
        }}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUpOrCancel}
        onPointerCancel={handlePointerUpOrCancel}
      >
        {/* Top 120 px HUD Band */}
        <header className="bb-hud-bar" style={{ height: `${TOP_BAND_HEIGHT}px` }}>
          <button
            type="button"
            className="bb-back-btn"
            onPointerDown={(e) => e.stopPropagation()}
            onClick={() => navigate("/bubbleblitzlevelselect")}
          >
            <img src={backImg} alt="Back to Level Select" className="bb-back-icon" />
          </button>

          <div className="bb-mode-badge">
            <img src={modeBannerImg} alt={modeTitle} className="bb-mode-banner-img" />
            <span className="bb-mode-title">{modeTitle}</span>
          </div>

          <div className="bb-hud-stat">
            <span className="bb-hud-label">TIME</span>
            <span className="bb-hud-value">{Math.ceil(secondsLeft)}s</span>
          </div>

          <div className="bb-hud-stat">
            <span className="bb-hud-label">SCORE</span>
            <span className="bb-hud-value">{score}</span>
          </div>

          <div className="bb-hud-stat">
            <span className="bb-hud-label">BEST</span>
            <span className="bb-hud-value">
              {highScore.bestScore} ({highScore.bestStars}★)
            </span>
          </div>

          <div className="bb-strikes-box" aria-label={`Strikes: ${strikes} of ${MAX_STRIKES}`}>
            {STRIKE_SLOTS.map((slot) => (
              <span
                key={slot}
                className={`bb-strike-x ${strikes >= slot ? "bb-strike-active" : ""}`}
              >
                ✕
              </span>
            ))}
          </div>
        </header>

        {/* Hard Mode 100 px Side Spike Strips */}
        {level === LEVEL_HARD && (
          <>
            <div
              className="bb-spike-strip bb-spike-left"
              style={{
                top: `${TOP_BAND_HEIGHT}px`,
                width: `${SPIKE_STRIP_WIDTH}px`,
                height: `${VIRTUAL_HEIGHT - TOP_BAND_HEIGHT}px`,
              }}
            >
              <img src={spikesImg} alt="Left Spikes" className="bb-spike-img" />
            </div>
            <div
              className="bb-spike-strip bb-spike-right"
              style={{
                top: `${TOP_BAND_HEIGHT}px`,
                width: `${SPIKE_STRIP_WIDTH}px`,
                height: `${VIRTUAL_HEIGHT - TOP_BAND_HEIGHT}px`,
              }}
            >
              <img src={spikesImg} alt="Right Spikes" className="bb-spike-img bb-spike-flip" />
            </div>
          </>
        )}

        {/* Active Bubbles */}
        {bubbles.map((b) => {
          const diameter = b.radius * DIAMETER_MULTIPLIER;
          const tapsRemaining = Math.max(MIN_TAPS_REMAINING, b.taps_needed - b.taps_done);
          return (
            <div
              key={b.id}
              className={`bb-bubble-wrapper bb-bubble-${b.type} ${
                b.is_held ? "bb-bubble-held" : ""
              }`}
              style={{
                left: `${b.x - b.radius}px`,
                top: `${b.y - b.radius}px`,
                width: `${diameter}px`,
                height: `${diameter}px`,
              }}
            >
              <img
                src={getBubbleImage(b)}
                alt={`${b.type} bubble`}
                className="bb-bubble-img"
                draggable={false}
              />

              {/* Medium Mode Multi-Tap Countdown Badge */}
              {level === LEVEL_MEDIUM && (
                <span className="bb-tap-counter">{tapsRemaining}</span>
              )}

              {/* Hard Mode Gesture Hint Badge */}
              {level === LEVEL_HARD && b.type !== "plain" && (
                <span className="bb-gesture-label">
                  {b.type === "drag" ? "⇄ DRAG" : "PINCH"}
                </span>
              )}
            </div>
          );
        })}

        {/* Floating Event Effects (Popped points, Expired, Strikes, Released) */}
        {effects.map((fx) => (
          <div
            key={fx.key}
            className={`bb-effect bb-effect-${fx.type}`}
            style={{ left: `${fx.x}px`, top: `${fx.y}px` }}
          >
            {fx.text}
          </div>
        ))}

        {/* 2-Step Level Intro Pop-Up */}
        {introStep !== null && (
          <div className="bb-overlay" onPointerDown={(e) => e.stopPropagation()}>
            <div className="bb-intro-card">
              <h2 className="bb-intro-title">
                {introStep === 1 ? introCopy.popTitle : introCopy.strikesTitle}
              </h2>
              <p className="bb-intro-text">
                {introStep === 1 ? introCopy.popText : introCopy.strikesText}
              </p>
              <button
                type="button"
                className="bb-intro-next-btn"
                onClick={() => setIntroStep(introStep === 1 ? 2 : null)}
              >
                {introStep === 1 ? "Next" : "Start!"}
              </button>
            </div>
          </div>
        )}

        {/* Loading Overlay */}
        {statusMessage && (
          <div className="bb-overlay" onPointerDown={(e) => e.stopPropagation()}>
            <div className="bb-modal-card">
              <h2>{statusMessage}</h2>
            </div>
          </div>
        )}

        {/* Friendly Error / Session Timeout Overlay (404 / 503) */}
        {errorModal && (
          <div className="bb-overlay" onPointerDown={(e) => e.stopPropagation()}>
            <div className="bb-modal-card">
              <h2>{errorModal.title}</h2>
              <p>{errorModal.message}</p>
              <div className="bb-modal-actions">
                <button type="button" className="bb-action-btn" onClick={() => void startNewLevel()}>
                  Start Fresh
                </button>
                <button
                  type="button"
                  className="bb-action-btn bb-secondary-btn"
                  onClick={() => navigate("/bubbleblitzlevelselect")}
                >
                  Level Select
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Win / Lose Results Overlay */}
        {finished && results && (
          <div className="bb-overlay" onPointerDown={(e) => e.stopPropagation()}>
            <div className="bb-modal-card">
              <h1 className="bb-result-title">
                {results.won ? "Great Job! You Won!" : "Nice Try!"}
              </h1>

              <div className="bb-stars-row" aria-label={`${results.stars} of ${MAX_STARS} stars`}>
                {STAR_SLOTS.map((starIndex) => (
                  <span
                    key={starIndex}
                    className={`bb-star ${
                      results.stars >= starIndex ? "bb-star-earned" : "bb-star-empty"
                    }`}
                  >
                    ★
                  </span>
                ))}
              </div>

              <div className="bb-results-summary">
                <p>
                  Score: <strong>{results.score}</strong>
                </p>
                <p>
                  Bubbles Popped: <strong>{results.popped_count}</strong>
                </p>
                <p>
                  Best Score: <strong>{highScore.bestScore}</strong> ({highScore.bestStars}★)
                </p>
              </div>

              <div className="bb-modal-actions">
                <button type="button" className="bb-action-btn" onClick={() => void startNewLevel()}>
                  Play Again
                </button>
                <button
                  type="button"
                  className="bb-action-btn bb-secondary-btn"
                  onClick={() => navigate("/bubbleblitzlevelselect")}
                >
                  Level Select
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default BubbleBlitzBoard;