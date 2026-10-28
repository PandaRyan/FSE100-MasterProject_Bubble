# Shared base game rules. Decides what is true: strikes, score, loss, win, results.
# Mode files (easybubble.py, mediummode, hardmode, survivalmode) subclass this and own
# the bubble list, spawning, and anything mode-specific.
# All times are in seconds.

class GameRules:
    # Stores the shared settings and starting state
    # Settings: width, height, level_duration, max_strikes, bubble_cap
    # State: strikes, score, popped_count, start_time, finished, won
    def __init__(self, width, height, level_duration, max_strikes, bubble_cap):
        pass

    # Records the raw start time and resets strikes, score, popped count, finished, won
    # Mode files extend this to spawn their first bubbles
    def start(self, current_time):
        pass

    # Called every tick. Ignored once the level is finished.
    # Flow: expire old bubbles (hook) -> strikes for expirations -> run spawn logic (hook)
    #       -> check_loss -> check_win
    def update(self, current_time):
        pass

    # Common tap flow. Ignored once the level is finished.
    # Flow: find the hit bubble among active bubbles
    #       -> hit: call on_bubble_hit; if it returns a pop, award points and count it
    #       -> miss on empty space: add_strike
    def handle_tap(self, tap_x, tap_y, tap_time):
        pass

    # Adds one strike, then checks for loss
    def add_strike(self):
        pass

    # Adds points to the score and increments popped_count
    def add_points(self, points):
        pass

    # True when strikes >= max_strikes
    def check_loss(self):
        pass

    # True when elapsed time >= level_duration and strikes < max_strikes
    def check_win(self, current_time):
        pass

    # Freezes the state, sets won/finished, and stores the final stars
    # Loss = 0 stars, win = at least 1 star
    def end_level(self, won):
        pass

    # Returns won, score, stars, strikes, popped count
    def get_results(self):
        pass

    # ---- Hooks each mode file must implement ----

    # Returns the list of active bubbles (the mode owns the list)
    def get_active_bubbles(self):
        pass

    # Removes expired bubbles and returns how many expired
    def expire_bubbles(self, current_time):
        pass

    # Mode spawn timer and pace logic
    def run_spawning(self, current_time):
        pass

    # Mode-specific reaction to a hit (easy: pop; medium: count a tap; hard: gesture check)
    # Returns whether the bubble was fully popped, and the reaction time if so
    def on_bubble_hit(self, bubble, tap_time):
        pass

    # Mode equation, clamped to 0-100
    def calculate_points(self, reaction_time):
        pass

    # Mode star thresholds from total score; returns 0-3 before the base class applies the floor
    def calculate_stars(self):
        pass