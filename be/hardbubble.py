import math
import random

from gamerules import GameRules
from bubbles import Bubble

# Hard mode:
#   Most bubbles pop with one tap. Drag bubbles are dragged until their edge touches a side spike strip.
#   Pinch bubbles are pinched (two fingers closing). Only one drag or pinch bubble is on screen at a time.
#   3 X's = lose
#   Survive 120 seconds to win

# Level Rules
LEVEL_DURATION = 120    # hard level length in seconds
MAX_STRIKES = 3         # 3 X's = loss
BUBBLE_CAP = 15         # on-screen cap for number of bubbles (20 felt like too much)

# Bubble types
PLAIN = "plain"
DRAG = "drag"
PINCH = "pinch"
TYPE_WEIGHTS = [70, 15, 15]                                    # intended % chance of plain, drag, pinch ("mostly plain")
BASE_LIFETIME = 5                                              # plain bubble lifetime in seconds (hard rule)
SPECIAL_LIFETIME_FACTOR = 1.25                                 # drag and pinch bubbles live 1.25x longer
SPECIAL_LIFETIME = BASE_LIFETIME * SPECIAL_LIFETIME_FACTOR     # 5 * 1.25 = 6.25 seconds

# Bubble size
# Usable width between the strips = 1920 - 2 * 100 = 1,720 and usable height = 1080 - 120 = 960, so area = 1,651,200 px^2
# r = sqrt(coverage * usable area / (cap * pi)) = sqrt(0.75 * 1,651,200 / (15 * 3.14159)) = 162.1 -> 162
RADIUS_MAX = 162                                # 15 bubbles this size would cover about 75% of the usable area
RADIUS_MIN = 81                                 # 50% of the max radius
RADIUS_SPLIT = (RADIUS_MIN + RADIUS_MAX) / 2    # 121.5, the middle of the range
BIG_RADIUS_CHANCE = 0.7                         # 70% of plain and pinch bubbles come from the bigger half (drag bubbles always do)

# Screen layout
TOP_BAND = 120                      # 120 px at the top is reserved for the strike counter and timer
SPIKE_STRIP = 100                   # 100 px strip on each side holds the spikes
DRAG_GAP_SHARE = 0.25               # drag bubbles spawn with their edge at least 25% of the usable width from each strip
                                    # (0.25 * 1,720 = 430 px, so every drag needs at least 430 px of travel)

# Spawning
PLACEMENT_ATTEMPTS = 10             # number of random spots tried before the spawn is skipped and retried next tick
FIRST_SPAWN_DELAY = 1.0             # grace period between starting the level and the first bubble spawn

# Gestures
PINCH_MIN_START_GAP = 40            # fingers must start at least 40 px apart (25% of the smallest 162 px diameter)
PINCH_CLOSE_SHARE = 0.5             # a pinch pops once the gap is at most 50% of the starting gap

# Points - hard equation: y = 112.213 - 22.3452x, x = reaction time in seconds
SCORE_INTERCEPT = 112.213
SCORE_SLOPE = -22.3452
MAX_POINTS = 100                    # Points have a range between 0-100 BEFORE the special multiplier
MIN_POINTS = 0
SPECIAL_MULTIPLIER = 1.5            # drag and pinch bubbles give 1.5x, applied after the clamp (max 150)

# Pace
START_INTERVAL = 3 / 4.5            # 4.5 bubbles per 3s, about 0.667s
MIN_INTERVAL = START_INTERVAL / 2   # ceiling pace = 2x the starting pace, about 0.333s
MAX_INTERVAL = START_INTERVAL       # hard never goes slower than the starting pace

# Score when the pace reaches 2x. Interval = START_INTERVAL / (1 + score / RAMP_SCORE), capped at 2x. Set to the 3-star score.
RAMP_SCORE = 19500

# Struggle Detection & Slowing
AVG_WINDOW = 5                      # reaction times averaged: the last 5 pops
EXPIRED_REACTION = 5                # an expired bubble counts as a 5s pop (equal to the base lifetime)
STRUGGLE_AVG = 3.0                  # 60% of the 5s lifetime = 3.0s (same ratio as easy and medium)
SLOW_STEP = 0.125                   # seconds added to the interval per bad event (about 19% of the start interval)
STRIKE_SLOW_STEP = 0.25             # step used once the player is at 2 strikes (twice the normal step)

# Recovery
RECOVER_FAST_AVG = 1.5              # average under this (3-star average) recovers fast
RECOVER_MAX_AVG = 2.5               # average above this does not recover (2-star average); 2.5-3.0s holds steady
RECOVER_FAST_STEP = 0.0625          # recovery per pop when the average is under 1.5s (half the slow step)
RECOVER_STEP = 0.03125              # recovery per pop when the average is 1.5-2.5s (a quarter of the slow step)
RECOVERY_POPS = 5                   # pops with no recovery after the 2nd strike (all modes)

# a 1.5s plain-tap average scores about 20,300 (every run reaches 19,500) and a 2.5s average scores about 10,900
THREE_STAR_SCORE = 19500            # a 1.5s plain-tap average just earns 3 stars (same number as RAMP_SCORE)
TWO_STAR_SCORE = 10500              # a 2.5s plain-tap average just earns 2 stars


class HardBubble(Bubble):
    # A hard-mode bubble: plain (one tap), drag (onto a side spike) or pinch (two fingers closing).
    # It stores its own type, home position and gesture state, chosen at spawn.
    def __init__(self, bubble_id, x, y, radius, spawn_time, lifetime, bubble_type):
        super().__init__(bubble_id, x, y, radius, spawn_time, lifetime)
        self.bubble_type = bubble_type  # PLAIN, DRAG or PINCH
        self.home_x = x                 
        self.home_y = y
        self.is_held = False            # True while a drag or pinch is in progress (a held bubble can't expire)
        self.start_gap = 0.0            # pinch only: finger gap when the pinch started


class HardBubbleGame(GameRules):
    # Constructor
    def __init__(self, width=1920, height=1080, rng=None):
        super().__init__(width, height, LEVEL_DURATION, MAX_STRIKES, BUBBLE_CAP)

        self.rng = rng if rng is not None else random.Random()

        self.bubbles = []
        self.next_bubble_id = 0
        self.has_spawned = False
        self.last_spawn_time = 0
        self.current_interval = START_INTERVAL
        self.is_slowed = False
        self.recent_reactions = []
        self.recovery_pops_left = 0
        self.drag_bubble = None         # the drag bubble being held, if any
        self.pinch_bubble = None        # the pinch bubble being held, if any
        self.stats = self._new_stats()

    # Resets and starts everything.
    # The first bubble spawns later, after FIRST_SPAWN_DELAY
    def start(self, current_time):
        super().start(current_time)
        self.bubbles = []
        self.next_bubble_id = 0
        self.has_spawned = False
        self.last_spawn_time = current_time
        self.current_interval = START_INTERVAL
        self.is_slowed = False
        self.recent_reactions = []
        self.recovery_pops_left = 0
        self.drag_bubble = None
        self.pinch_bubble = None
        self.stats = self._new_stats()

    # Counters for testing and simulation only. They never affect the game.
    def _new_stats(self):
        return {"spawned": {PLAIN: 0, DRAG: 0, PINCH: 0},
                "blocked_specials": 0,      # a drag/pinch was picked but a special was already on screen
                "spawn_tries": 0,           # spawn attempts that got as far as looking for a spot
                "placement_fails": 0}       # attempts where all PLACEMENT_ATTEMPTS spots overlapped

    # Hooks required by GameRules

    # Plain bubbles come first so a tap on overlapping bubbles pops the plain one.
    # (A dragged bubble can sit on top of other bubbles, and a tap on a drag or pinch bubble does nothing.)
    def get_active_bubbles(self):
        plain = [b for b in self.bubbles if b.bubble_type == PLAIN]
        special = [b for b in self.bubbles if b.bubble_type != PLAIN]
        return plain + special

    # Removes expired bubbles. A held bubble (drag or pinch in progress) can't expire.
    # Each expiry records a 5s reaction and adds a strike.
    def expire_bubbles(self, current_time):
        for bubble in list(self.bubbles):
            if bubble.is_held:
                continue
            if bubble.is_expired(current_time):
                self.remove_bubble(bubble)
                self._record_reaction(EXPIRED_REACTION)
                self.add_strike()       # our override below also slows the pace
                if self.finished:       # 3rd strike ends the level
                    break

    # Spawns when the time since the last spawn reaches the current interval.
    # If the cap is full or no spot is found, the spawn stays due and is retried on the next tick,
    # so it happens as soon as a slot opens and then restarts the full interval.
    def run_spawning(self, current_time):
        self._sync_interval()
        if not self.has_spawned:
            due = current_time - self.start_time >= FIRST_SPAWN_DELAY
        else:
            due = current_time - self.last_spawn_time >= self.current_interval

        if due and self.spawn_bubble(current_time):
            self.last_spawn_time = current_time
            self.has_spawned = True

    # A tap pops a plain bubble. A tap on a drag or pinch bubble is the wrong gesture and is ignored (no strike).
    def on_bubble_hit(self, bubble, tap_time):
        if bubble.bubble_type != PLAIN:
            return
        reaction = bubble.reaction_time(tap_time)
        self.pop_bubble(bubble)
        self.add_points(self.calculate_points(reaction))
        self._after_pop(reaction)

    # Hard equation clamped to 0-100, then multiplied for drag and pinch bubbles
    def calculate_points(self, reaction_time, special=False):
        base = SCORE_INTERCEPT + SCORE_SLOPE * reaction_time
        base = max(MIN_POINTS, min(MAX_POINTS, base))
        if special:
            return base * SPECIAL_MULTIPLIER
        return base

    # Raw 0-3 from the total score
    # GameRules raises any win to at least 1 star.
    def calculate_stars(self):
        if self.score >= THREE_STAR_SCORE:
            return 3
        elif self.score >= TWO_STAR_SCORE:
            return 2

        return 0

    # Strikes

    # A strike (empty tap or expiry) also slows the pace. The 2nd strike starts the 5-pop period with no recovery.
    def add_strike(self):
        if self.finished:
            return
        super().add_strike()
        if self.finished:
            return
        self._slow(self._slow_step())
        if self.strikes == MAX_STRIKES - 1:
            self.recovery_pops_left = RECOVERY_POPS

    # Gestures (drag and pinch). Taps go through GameRules.handle_tap.
    # A gesture that starts on the wrong bubble, or on empty space, is ignored (no strike).

    # True if the call must be ignored. A gesture at or after the end time pops nothing and ends the level.
    def _gesture_blocked(self, event_time):
        if self.finished:
            return True
        if event_time - self.start_time >= self.level_duration:
            self.end_level(self.check_win(event_time))
            return True
        return False

    # A finger that moved starts a drag where it first landed. It must land inside a free drag bubble.
    def handle_drag_start(self, x, y, t):
        if self._gesture_blocked(t):
            return
        if self.drag_bubble is not None:
            return
        for bubble in self.bubbles:
            if bubble.bubble_type == DRAG and not bubble.is_held and bubble.contains_point(x, y):
                bubble.is_held = True
                self.drag_bubble = bubble
                self._move_drag(bubble, x, y, t)
                return

    # The held bubble's center follows the finger
    def handle_drag_move(self, x, y, t):
        if self._gesture_blocked(t):
            return
        if self.drag_bubble is not None:
            self._move_drag(self.drag_bubble, x, y, t)

    # The finger lifted. If the bubble is not on a spike it goes home and its lifetime and reaction clock restart.
    def handle_drag_end(self, x, y, t):
        if self._gesture_blocked(t):
            return
        bubble = self.drag_bubble
        if bubble is None:
            return
        if self._move_drag(bubble, x, y, t):
            return
        self._release(bubble, t)

    # Two fingers landing together start a pinch. Both must be inside a free pinch bubble and far enough apart.
    def handle_pinch_start(self, x1, y1, x2, y2, t):
        if self._gesture_blocked(t):
            return
        if self.pinch_bubble is not None:
            return
        gap = math.hypot(x2 - x1, y2 - y1)
        if gap < PINCH_MIN_START_GAP:
            return
        for bubble in self.bubbles:
            if bubble.bubble_type == PINCH and not bubble.is_held \
                    and bubble.contains_point(x1, y1) and bubble.contains_point(x2, y2):
                bubble.is_held = True
                bubble.start_gap = gap
                self.pinch_bubble = bubble
                return

    # The pinch pops the moment the gap closes to PINCH_CLOSE_SHARE of its starting gap
    def handle_pinch_move(self, x1, y1, x2, y2, t):
        if self._gesture_blocked(t):
            return
        if self.pinch_bubble is not None:
            self._check_pinch(self.pinch_bubble, x1, y1, x2, y2, t)

    # The fingers lifted. If the gap never closed, the bubble is released and its lifetime and reaction clock restart.
    def handle_pinch_end(self, x1, y1, x2, y2, t):
        if self._gesture_blocked(t):
            return
        bubble = self.pinch_bubble
        if bubble is None:
            return
        if self._check_pinch(bubble, x1, y1, x2, y2, t):
            return
        self._release(bubble, t)

    # Moves the held drag bubble to the finger (y kept inside the play area) and pops it if its edge touches a strip.
    # Returns True if it popped.
    def _move_drag(self, bubble, x, y, t):
        bubble.x = x
        bubble.y = max(TOP_BAND + bubble.radius, min(self.height - bubble.radius, y))
        if bubble.x - bubble.radius <= SPIKE_STRIP or bubble.x + bubble.radius >= self.width - SPIKE_STRIP:
            self._pop_special(bubble, t)
            return True
        return False

    # Pops the held pinch bubble if the finger gap is small enough. Returns True if it popped.
    def _check_pinch(self, bubble, x1, y1, x2, y2, t):
        gap = math.hypot(x2 - x1, y2 - y1)
        if gap <= PINCH_CLOSE_SHARE * bubble.start_gap:
            self._pop_special(bubble, t)
            return True
        return False

    # Scores a drag or pinch bubble (reaction time ends at the spike touch or the closed pinch)
    def _pop_special(self, bubble, t):
        reaction = bubble.reaction_time(t)
        self.pop_bubble(bubble)
        self.add_points(self.calculate_points(reaction, True))
        self._after_pop(reaction)

    # Lets go of a held bubble: it returns home and its lifetime and reaction clock restart
    def _release(self, bubble, t):
        bubble.x = bubble.home_x
        bubble.y = bubble.home_y
        bubble.spawn_time = t
        bubble.is_held = False
        bubble.start_gap = 0.0
        self._clear_held(bubble)

    # Forgets a bubble that is no longer being held
    def _clear_held(self, bubble):
        if self.drag_bubble is bubble:
            self.drag_bubble = None
        if self.pinch_bubble is bubble:
            self.pinch_bubble = None

    # Bubbles

    # True if a drag or pinch bubble is already on screen
    def _special_on_screen(self):
        for bubble in self.bubbles:
            if bubble.bubble_type != PLAIN:
                return True
        return False

    # Picks plain, drag or pinch using TYPE_WEIGHTS. Only one special at a time, so a blocked pick becomes plain.
    # Returns (type, blocked).
    def _pick_type(self):
        bubble_type = self.rng.choices([PLAIN, DRAG, PINCH], weights=TYPE_WEIGHTS)[0]
        if bubble_type != PLAIN and self._special_on_screen():
            return PLAIN, True
        return bubble_type, False

    # Picks a radius: drag bubbles always come from the big half. Others: 70% big half, 30% small half.
    def _pick_radius(self, bubble_type):
        if bubble_type == DRAG or self.rng.random() < BIG_RADIUS_CHANCE:
            return round(self.rng.uniform(RADIUS_SPLIT, RADIUS_MAX))
        return round(self.rng.uniform(RADIUS_MIN, RADIUS_SPLIT))

    # Picks the bubble's type and size, then tries PLACEMENT_ATTEMPTS random spots
    # and rejects any that overlap an active bubble. Returns True if a bubble was added.
    def spawn_bubble(self, current_time):
        if len(self.bubbles) >= BUBBLE_CAP:
            return False
        bubble_type, blocked = self._pick_type()
        radius = self._pick_radius(bubble_type)
        lifetime = BASE_LIFETIME if bubble_type == PLAIN else SPECIAL_LIFETIME
        x_min = SPIKE_STRIP + radius
        x_max = self.width - SPIKE_STRIP - radius
        if bubble_type == DRAG:
            gap = DRAG_GAP_SHARE * (self.width - 2 * SPIKE_STRIP)
            x_min += gap
            x_max -= gap
        y_min = TOP_BAND + radius
        y_max = self.height - radius
        if x_min > x_max or y_min > y_max:      # screen too small for this bubble
            return False
        self.stats["spawn_tries"] += 1
        for _ in range(PLACEMENT_ATTEMPTS):
            x = self.rng.uniform(x_min, x_max)
            y = self.rng.uniform(y_min, y_max)
            if not self._overlaps(x, y, radius):
                bubble = HardBubble(self.next_bubble_id, x, y, radius,
                                    current_time, lifetime, bubble_type)
                self.next_bubble_id += 1
                self.bubbles.append(bubble)
                self.stats["spawned"][bubble_type] += 1
                if blocked:
                    self.stats["blocked_specials"] += 1
                return True
        self.stats["placement_fails"] += 1
        return False

    # Takes a popped bubble out of play
    def pop_bubble(self, bubble):
        self.remove_bubble(bubble)

    # Deactivates a bubble and takes it out of the list (popped or expired)
    def remove_bubble(self, bubble):
        bubble.is_active = False
        bubble.is_held = False
        self._clear_held(bubble)
        if bubble in self.bubbles:
            self.bubbles.remove(bubble)

    # True if a bubble of this radius centered at (x, y) would overlap an active bubble.
    # Every bubble counts at its home position, so a dragged bubble's current spot is skipped
    # and its home stays reserved for when it is released.
    def _overlaps(self, x, y, radius):
        for other in self.bubbles:
            dx = x - other.home_x
            dy = y - other.home_y
            min_dist = radius + other.radius
            if dx * dx + dy * dy < min_dist * min_dist:
                return True
        return False

    # Pacing

    # Interval the score alone asks for: about 0.667s at 0 points down to about 0.333s at RAMP_SCORE
    def _points_interval(self):
        return START_INTERVAL / (1 + min(self.score / RAMP_SCORE, 1))

    # While not slowed, the interval follows the points-based one
    def _sync_interval(self):
        if not self.is_slowed:
            self.current_interval = self._points_interval()

    # Step size for a bad event: bigger once the player is at 2 strikes
    def _slow_step(self):
        if self.strikes >= MAX_STRIKES - 1:
            return STRIKE_SLOW_STEP
        return SLOW_STEP

    # Lengthens the interval by one step, capped at MAX_INTERVAL (the starting pace)
    def _slow(self, step):
        if not self.is_slowed:
            self.current_interval = self._points_interval()
        self.current_interval = min(MAX_INTERVAL, self.current_interval + step)
        self.is_slowed = True

    # Shortens the interval by one step, never below the points-based interval
    def _recover(self, step):
        if not self.is_slowed:
            return
        self.current_interval -= step
        target = self._points_interval()
        if self.current_interval <= target:
            self.current_interval = target
            self.is_slowed = False

    # Keeps only the last AVG_WINDOW reaction times
    def _record_reaction(self, reaction):
        self.recent_reactions.append(reaction)
        if len(self.recent_reactions) > AVG_WINDOW:
            self.recent_reactions.pop(0)

    # Returns the average reaction time
    def _average_reaction(self):
        return sum(self.recent_reactions) / len(self.recent_reactions)

    # After a pop: slow if struggling, hold during the 2-strike period, hold between 2.5s and 3.0s, otherwise recover
    def _after_pop(self, reaction):
        self._record_reaction(reaction)
        avg = self._average_reaction()
        if avg > STRUGGLE_AVG:
            self._slow(self._slow_step())
        elif self.recovery_pops_left > 0:
            pass                               # stay put until all 5 pops are done
        elif avg < RECOVER_FAST_AVG:
            self._recover(RECOVER_FAST_STEP)
        elif avg <= RECOVER_MAX_AVG:
            self._recover(RECOVER_STEP)

        # 2.5s < avg <= 3.0s: hold steady
        if self.recovery_pops_left > 0:
            self.recovery_pops_left -= 1