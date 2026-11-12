import random

from gamerules import GameRules
from bubbles import Bubble

# Medium mode:
#   Bubbles need 1-5 taps. The lifetime keeps runing and the reaction time ends on the final tap
#   3 X's = lose
#   Survive 90 seconds to win

# Level Rules:
LEVEL_DURATION = 90     # Medium level time length in seconds
MAX_STRIKES = 3         
BUBBLE_CAP = 15         # on-screen cap for number of bubbles

# Taps and lifetime
TAP_WEIGHTS = [30, 25, 20, 15, 10]  # % Chance of 1, 2, 3, 4, 5 taps
BASE_LIFETIME = 7                   # Lifetime of a bubble, but could be added to based on number of taps it takes to pop a bubble
LIFETIME_PER_EXTRA_TAP = 1          # Each extra tap adds 1 second

# Bubble Size
# Usuable area = 1920 * 960 (not 1080 because of top band) = 1,843,200 px^2
# r = sqrt (coverage * usuable area / (cap * pi))
RADIUS_MAX = 171        # If all 15 bubbles were this radius it would cover about 75% of the screen
RADIUS_MIN = 86         # 50% of the max radius
RADIUS_SPLIT = (RADIUS_MIN + RADIUS_MAX) / 2
BIG_RADIUS_CHANCE = 0.7     # 70% of the bubbles come from the bigger half of the split
TOP_BAND = 120              # 120 px at the top is reserved for the strike counter and timer

# Spawning
PLACEMENT_ATTEMPTS = 10     # number of times a spot tries to spawn a bubble before a new spot is chosen
FIRST_SPAWN_DELAY = 1.0     # grace period in between starting the level and the first bubble spawn

# Points - medium equation: y = 105.825 - 14.9985x, x = reaction time in seconds
SCORE_INTERCEPT = 105.825
SCORE_SLOPE = -14.9985
MAX_POINTS = 100            # Points have a range between 0-100 BEFORE the tap multiplier
MIN_POINTS = 0
# Havling idea: 1st tap full points, 2nd tap 1/2, 3rd 1/4, and so on
TAP_MULTIPLIERS = [1, 1.5, 1.75, 1.875, 1.9375]

# Pace
START_INTERVAL = 1.2        # 2.5 bubbles per 3s = 3 / 2.5
MIN_INTERVAL = 0.6          # ceiling pace = 2x the starting pace
MAX_INTERVAL = 1.2          # medium never goes slower than the starting pace
# Score when the pace reaches 2x. Interval = 1.2 / (1 + score / RAMP_SCORE), capped at 2x. Set to the 3-star score.
RAMP_SCORE = 11000

# Struggle Detection & Slowing
AVG_WINDOW = 5            # Reaction times averaged: the last 5 pops
EXPIRED_REACTION = 7      # an expired bubble counts as 7s to pop a bubble
STRUGGLE_AVG = 4.0        # 60% of 7s = 4.2s, rounded to 4 seconds
SLOW_STEP = 0.25          # Number of seconds added to the interval per bad event
STRIKE_SLOW_STEP = 0.5    # Step used once the player is at 2 strikes

# Recovery
RECOVER_FAST_AVG = 2.0      # average under this (3-star pace) recovers fast: easy's 3s scaled by 7/10, rounded to a half second
RECOVER_MAX_AVG = 3.5       # average above this does not recover (the 2-star average)
RECOVER_FAST_STEP = 0.25    # recovery per pop when the average is under 2s (decided)
RECOVER_STEP = 0.125        # recovery per pop when the average is 2-3.5s (decided)
RECOVERY_POPS = 5           # pops with no recovery after the 2nd strike (all modes)

# Stars - from full simulated levels (200 seeds, reaction spread 0.30):
# a 2.0s average scores about 11,550 (94% of runs reach 11,000) and a 3.5s average scores about 6,360
# (75% of runs reach 6,000), so the lines are those scores rounded DOWN to clean numbers.
THREE_STAR_SCORE = 11000    # a 2.0s average reaction just earns 3 stars (same number as RAMP_SCORE)
TWO_STAR_SCORE = 6000       # a 3.5s average reaction just earns 2 stars


class MediumBubble(Bubble):
    # A bubble taht needs several taps.
    # It stores its own tap count, chosen at spawn
    def __init__(self, bubble_id, x, y, radius, spawn_time, lifetime, tap_count):
        super().__init__(bubble_id, x, y, radius, spawn_time, lifetime)
        self.tap_count = tap_count      # taps needed to pop it (1-5)
        self.taps_done = 0              # taps received so far

class MediumBubbleGame(GameRules):
    # Constructor
    def __init__(self, width = 1920, height = 1080, rng = None):
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
        self.taps_registered = 0

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
        self.taps_registered = 0

    # Hooks required by GameRules

    def get_active_bubbles(self):
        return self.bubbles

    # Removes expired bubbles
    # Each one records a 7s reaction and adds a strike
    def expire_bubbles(self, current_time):
        for bubble in list(self.bubbles):
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

    # A tap on a medium bubble counts one tap. Only the final tap pops it, scores it and updates the pacing.
    def on_bubble_hit(self, bubble, tap_time):
        self.taps_registered += 1
        bubble.taps_done += 1

        if bubble.taps_done < bubble.tap_count:
            return

        reaction = bubble.reaction_time(tap_time)
        self.pop_bubble(bubble)
        self.add_points(self.calculate_points(reaction, bubble.tap_count))
        self._after_pop(reaction)

    # Medium equation clamped to 0-100, then multiplied by the tap-count multiplier
    def calculate_points(self, reaction_time, tap_count =1 ):
        base = SCORE_INTERCEPT + SCORE_SLOPE * reaction_time
        base = max(MIN_POINTS, min(MAX_POINTS, base))
        return base * TAP_MULTIPLIERS[tap_count - 1]

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

    # Bubbles

    # Picks 1-5 taps using TAP_WEIGHTS
    def _pick_tap_count(self):
        return self.rng.choices([1, 2, 3, 4, 5], weights=TAP_WEIGHTS)[0]

    # Picks a radius: 70% from the big half of the range, 30% from the small half
    def _pick_radius(self):
        if self.rng.random() < BIG_RADIUS_CHANCE:
            return round(self.rng.uniform(RADIUS_SPLIT, RADIUS_MAX))
        return round(self.rng.uniform(RADIUS_MIN, RADIUS_SPLIT))

    # Picks the bubble's tap count and size, then tries PLACEMENT_ATTEMPTS random spots
    # and rejects any that overlap an active bubble. Returns True if a bubble was added.
    def spawn_bubble(self, current_time):
        if len(self.bubbles) >= BUBBLE_CAP:
            return False
        tap_count = self._pick_tap_count()
        radius = self._pick_radius()
        lifetime = BASE_LIFETIME + LIFETIME_PER_EXTRA_TAP * (tap_count - 1)
        x_min = radius
        x_max = self.width - radius
        y_min = TOP_BAND + radius
        y_max = self.height - radius
        for _ in range(PLACEMENT_ATTEMPTS):
            x = self.rng.uniform(x_min, x_max)
            y = self.rng.uniform(y_min, y_max)
            if not self._overlaps(x, y, radius):
                bubble = MediumBubble(self.next_bubble_id, x, y, radius,
                                      current_time, lifetime, tap_count)
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

    # True if a bubble of this radius centered at (x, y) would overlap an active bubble
    def _overlaps(self, x, y, radius):
        for other in self.bubbles:
            dx = x - other.x
            dy = y - other.y
            min_dist = radius + other.radius
            if dx * dx + dy * dy < min_dist * min_dist:
                return True
        return False

    # Pacing

    # Interval the score alone asks for: 1.2s at 0 points down to 0.6s at RAMP_SCORE
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

    def _average_reaction(self):
        return sum(self.recent_reactions) / len(self.recent_reactions)

    # After a pop: slow if struggling, hold during the 2-strike period, hold between 3.5s and 4s, otherwise recover
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

        # 3.5s < avg <= 4s: hold steady
        if self.recovery_pops_left > 0:
            self.recovery_pops_left -= 1