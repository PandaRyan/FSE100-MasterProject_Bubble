# gamerules.py
# Shared base game rules. Decides what is true: strikes, score, loss, win, results.
# Mode files subclass this and own the bubble list, spawning, points, and expirations.
# All times are in seconds.

class GameRules:
    def __init__(self, width, height, level_duration, max_strikes, bubble_cap):
        self.width = width
        self.height = height
        self.level_duration = level_duration
        self.max_strikes = max_strikes
        self.bubble_cap = bubble_cap

        self.strikes = 0
        self.score = 0
        self.popped_count = 0
        self.start_time = 0
        self.finished = False
        self.won = False
        self.stars = 0

    # Records the raw start time and resets all state
    # Mode files call super().start(current_time), then spawn their first bubbles
    def start(self, current_time):
        self.start_time = current_time
        self.strikes = 0
        self.score = 0
        self.popped_count = 0
        self.finished = False
        self.won = False
        self.stars = 0

    # Called every tick. Ignored once the level is finished.
    def update(self, current_time):
        if self.finished:
            return

        # Time's up is checked first, so an expiration on the final instant can't add a strike
        if current_time - self.start_time >= self.level_duration:
            self.end_level(self.check_win(current_time))
            return

        self.expire_bubbles(current_time)   # mode calls add_strike itself
        if self.finished:                   # a strike may have ended the level
            return

        self.run_spawning(current_time)

    # Common tap flow. Ignored once the level is finished.
    def handle_tap(self, tap_x, tap_y, tap_time):
        if self.finished:
            return

        # A tap at or after the end time can't pop anything
        if tap_time - self.start_time >= self.level_duration:
            self.end_level(self.check_win(tap_time))
            return

        for bubble in self.get_active_bubbles():
            if bubble.contains_point(tap_x, tap_y):
                self.on_bubble_hit(bubble, tap_time)   # mode scores it if fully popped
                return

        # Tapped empty space
        self.add_strike()

    # Adds one strike, then ends the level if that was the last one
    def add_strike(self):
        if self.finished:
            return
        self.strikes += 1
        if self.check_loss():
            self.end_level(False)

    # Rounds the points, adds them to the score, and counts the pop
    def add_points(self, points):
        if self.finished:
            return
        self.score += round(points)
        self.popped_count += 1

    # True when strikes have reached the limit
    def check_loss(self):
        return self.strikes >= self.max_strikes

    # True when time is up and strikes are below the limit
    def check_win(self, current_time):
        time_up = current_time - self.start_time >= self.level_duration
        return time_up and self.strikes < self.max_strikes

    # Freezes the state. Loss = 0 stars, win = at least 1 star.
    def end_level(self, won):
        if self.finished:
            return
        self.finished = True
        self.won = won
        self.stars = max(1, self.calculate_stars()) if won else 0

    # Everything the frontend needs, so it never recalculates
    def get_results(self):
        return {
            "won": self.won,
            "score": self.score,
            "stars": self.stars,
            "strikes": self.strikes,
            "popped_count": self.popped_count,
        }

    # ---- Gesture hooks (used by hard mode) ----
    # Default no-ops, so easy and medium ignore gestures. Hard overrides all six.
    # Drag events carry one finger position; pinch events carry both. t is the raw event time in seconds.

    # A finger that moved starts a drag where it first landed
    def handle_drag_start(self, x, y, t):
        pass

    # The dragging finger moved
    def handle_drag_move(self, x, y, t):
        pass

    # The dragging finger lifted
    def handle_drag_end(self, x, y, t):
        pass

    # Two fingers landed together
    def handle_pinch_start(self, x1, y1, x2, y2, t):
        pass

    # Either finger of the pinch moved
    def handle_pinch_move(self, x1, y1, x2, y2, t):
        pass

    # The pinching fingers lifted
    def handle_pinch_end(self, x1, y1, x2, y2, t):
        pass

    # ---- Hooks each mode file must implement ----

    # Returns the list of active bubbles (the mode owns the list)
    def get_active_bubbles(self):
        raise NotImplementedError

    # Removes expired bubbles and calls add_strike() once for each
    def expire_bubbles(self, current_time):
        raise NotImplementedError

    # Mode spawn timer and pace logic
    def run_spawning(self, current_time):
        raise NotImplementedError

    # Mode reaction to a hit. If the bubble is fully popped, it calls pop_bubble,
    # then add_points(calculate_points(reaction_time))
    def on_bubble_hit(self, bubble, tap_time):
        raise NotImplementedError

    # Mode equation, clamped to 0-100
    def calculate_points(self, reaction_time):
        raise NotImplementedError

    # Mode star thresholds from total score; returns a raw 0-3
    def calculate_stars(self):
        raise NotImplementedError