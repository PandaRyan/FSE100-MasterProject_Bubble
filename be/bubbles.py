# Base class for one bubble. Holds per-bubble data and behavior only.
# The mode files own the bubble list, spawning, overlap checks, ids, and popping.
# All times are in seconds.

class Bubble:
    # The mode file passes in final values (id, center, radius, spawn time, lifetime)
    def __init__(self, bubble_id, x, y, radius, spawn_time, lifetime):
        self.bubble_id = bubble_id
        self.x = x                    # center x
        self.y = y                    # center y
        self.radius = radius
        self.spawn_time = spawn_time  # raw time the frontend/mode gave us
        self.lifetime = lifetime      # seconds the bubble lives
        self.is_active = True         # mode file's pop_bubble sets this to False

    # Hit test: edge counts as a hit, inactive bubbles never hit
    def contains_point(self, tap_x, tap_y):
        if not self.is_active:
            return False
        dx = tap_x - self.x
        dy = tap_y - self.y
        return dx * dx + dy * dy <= self.radius * self.radius

    # Seconds between spawn and the tap
    def reaction_time(self, tap_time):
        return tap_time - self.spawn_time

    # Expired once it has lived its full lifetime (age >= lifetime)
    def is_expired(self, current_time):
        return current_time - self.spawn_time >= self.lifetime