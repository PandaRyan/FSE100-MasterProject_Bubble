import random

from gamerules import GameRules
from bubbles import Bubble

# This will be the class for the easy mode:
#   Tap a bubble to pop it. 
#   3 X's = lose
#   Survive 60 seconds to win

# Level Rules
LEVEL_DURATION = 60
MAX_STRIKES = 3
BUBBLE_LIFETIME = 10
BUBBLE_CAP = 10

# Bubble size
# usable area = 1920 * 960 = 1,843,200 px^2 (1920x1080 minus the 120 px top band)
# r = sqrt(coverage * usable / (cap * pi)) = sqrt(0.5 * 1,843,200 / (10 * 3.14159)) = 171.28 -> 171
# 50% coverage at the cap was chosen for easy.
RADIUS = 171
# pi * r^2 with pi = 3.14159, so 10 bubbles cover 918,632 px^2, about 49.8% of the usable area
AREA = 91863.233
# 120 px at the top is reserved for the strike counter and timer
TOP_BAND = 120

# Spawning
PLACEMENT_ATTEMPTS = 10
FIRST_SPAWN_DELAY = 1.0

# Points - easy equation: y = 106.041 - 10.0240x, x = reaction time in seconds
SCORE_INTERCEPT = 106.041
SCORE_SLOPE = -10.024
MAX_POINTS = 100
MIN_POINTS = 0

# Pace
START_INTERVAL = 3.0    # Starting interval between bubble spawns
MIN_INTERVAL = 1.5      # Ceiling interval between bubble spawns (Towards the end of the level and only if the player has faster reaction times)
MAX_INTERVAL = 6.0      # Floor interval between bubble spawns (Reached when the player is struggling: 5-pop average above 6s, or repeated strikes)
# Score where the pace reaches 2x. Interval = 3 (Starting interval) / (1 + score / RAMP_SCORE), capped at 2x.
# 2150 makes a 1.5s-average player hit 2x about 10s before the end and a 2.5s-average player about 5s before the end of the level.
RAMP_SCORE = 2150

# Struggle Detection & Slowing
AVG_WINDOW = 5             # reaction times averaged: the last 5 pops
EXPIRED_REACTION = 10      # an expired bubble counts as a 10s pop (equal to the lifetime)
STRUGGLE_AVG = 6.0         # average above this = struggling (bottom of the 2-star range)
SLOW_STEP = 1.0            # seconds added to the interval per bad event
STRIKE_SLOW_STEP = 1.5     # step used once the player is at 2 strikes (Designed to make the game not too dificult for toddlers)

# Recovery
RECOVER_FAST_AVG = 3.0     # average under this (3-star pace) recovers by 1.0s per pop
RECOVER_MAX_AVG = 5.0      # average above this does not recover (the 2-star average)
RECOVER_FAST_STEP = 1.0    # recovery per pop when the average is under 3s
RECOVER_STEP = 0.5         # recovery per pop when the average is 3-5s
RECOVERY_POPS = 5          # pops with no recovery after the 2nd strike

# Stars - from full simulated levels in this file's real code (mean of 10 seeds):
# a 3.5s average scores 1,774-1,775 and a 5.9s average scores 978-987, so the thresholds are
# those scores rounded DOWN to clean numbers, keeping both target players on the right side.
THREE_STAR_SCORE = 1750    # a 3.5s average reaction just earns 3 stars
TWO_STAR_SCORE = 950       # a 5.9s average reaction (just under the 6s struggle line) just earns 2 stars

class EasyBubbleGame(GameRules):
    # Constructor: shared settings go to GameRules; this mode adds the bubble list, spawn timer and pacing state
    # bubbles is a list of Bubble objects (this mode owns the list)
    def __init__(self, width=1920, height=1080, rng=None):
        super().__init__(width, height, LEVEL_DURATION, MAX_STRIKES, BUBBLE_CAP)

        self.rng = rng if rng is not None else random.Random()

        self.x_min = RADIUS
        self.x_max = width - RADIUS
        self.y_min = TOP_BAND + RADIUS
        self.y_max = height - RADIUS

        self.bubbles = []
        self.next_bubble_id = 0
        self.has_spawned = False
        self.last_spawn_time = 0
        self.current_interval = START_INTERVAL
        self.is_slowed = False
        self.recent_reactions = []
        self.recovery_pops_left = 0

    # Resets everything. The first bubble spawns later, after FIRST_SPAWN_DELAY.
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

    # Hooks required by GameRules 

    def get_active_bubbles(self):
        return self.bubbles

    # Removes expired bubbles. Each one records a 10s reaction and adds a strike.
    def expire_bubbles(self, current_time):
        for bubble in list(self.bubbles):
            if bubble.is_expired(current_time):
                self.remove_bubble(bubble)
                self._record_reaction(EXPIRED_REACTION)
                self.add_strike()       # our override below also slows the pace
                if self.finished:       # the 3rd strike ended the level
                    break

    # Spawns when the time since the last spawn reaches the current interval.
    # A failed spawn (cap full or no spot found) is retried on the next tick.
    def run_spawning(self, current_time):
        self._sync_interval()
        if not self.has_spawned:
            due = current_time - self.start_time >= FIRST_SPAWN_DELAY
        else:
            due = current_time - self.last_spawn_time >= self.current_interval
        if due and self.spawn_bubble(current_time):
            self.last_spawn_time = current_time
            self.has_spawned = True

    # One tap pops an easy bubble: remove it, score it, then update the pacing
    def on_bubble_hit(self, bubble, tap_time):
        reaction = bubble.reaction_time(tap_time)
        self.pop_bubble(bubble)
        self.add_points(self.calculate_points(reaction))
        self._after_pop(reaction)

    # Easy equation clamped to 0-100
    def calculate_points(self, reaction_time):
        points = SCORE_INTERCEPT + SCORE_SLOPE * reaction_time
        return max(MIN_POINTS, min(MAX_POINTS, points))

    # Raw 0-3 from the total score. GameRules raises any win to at least 1 star.
    def calculate_stars(self):
        if self.score >= THREE_STAR_SCORE:
            return 3
        if self.score >= TWO_STAR_SCORE:
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

    # Bubbles

    # Tries PLACEMENT_ATTEMPTS random spots, rejects any that overlap an active bubble.
    # Returns True if a bubble was added.
    def spawn_bubble(self, current_time):
        if len(self.bubbles) >= BUBBLE_CAP:
            return False
        for _ in range(PLACEMENT_ATTEMPTS):
            x = self.rng.uniform(self.x_min, self.x_max)
            y = self.rng.uniform(self.y_min, self.y_max)
            if not self._overlaps(x, y):
                bubble = Bubble(self.next_bubble_id, x, y, RADIUS,
                                current_time, BUBBLE_LIFETIME)
                self.next_bubble_id += 1
                self.bubbles.append(bubble)
                return True
        return False

    # Takes a popped bubble out of play
    def pop_bubble(self, bubble):
        self.remove_bubble(bubble)

    # Deactivates a bubble and takes it out of the list (popped or expired)
    def remove_bubble(self, bubble):
        bubble.is_active = False
        if bubble in self.bubbles:
            self.bubbles.remove(bubble)

    # True if a bubble centered at (x, y) would overlap an active bubble
    def _overlaps(self, x, y):
        for other in self.bubbles:
            dx = x - other.x
            dy = y - other.y
            min_dist = RADIUS + other.radius
            if dx * dx + dy * dy < min_dist * min_dist:
                return True
        return False

    # Pacing

    # Interval the score alone asks for: 3s at 0 points down to 1.5s at RAMP_SCORE
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

    # Lengthens the interval by one step, capped at MAX_INTERVAL
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

    def _average_reaction(self):
        return sum(self.recent_reactions) / len(self.recent_reactions)

    # After a pop: slow if struggling, hold during the 2-strike period, hold between 5s and 6s, otherwise recover
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

        # 5s < avg <= 6s: hold steady
        if self.recovery_pops_left > 0:
            self.recovery_pops_left -= 1