# This will be the class for the easy mode:
#   Tap a bubble to pop it. 
#   3 X'a = lose
#   Survive 60 seconds to win

# Constraints:
#   LEVEL_DURATION, MAX_STRIKES, BUBBLE_LIFETIME
#   SCORE_SLOPE, SLOPE_INTERCEPT (obtained from the star files equations)
#   MAX_POINTS_PER_BUBBLE, MIN_POINTS_PER_BUBBLE
#   STAR_THRESHOLDS (what earns 1, 2, or 3 stars)

# Class for one bubble hitbox
class Bubble:
    # Constructor to store: position, size, spawn time, and is_active flag
    def __init__(self, bubble_id, x, y, radius, spawn_time):
        self.bubble_id = 0
        self.x = 0
        self.y = 0
        self.radius = 1
        self.spawn_time = 0
        self.is_active = True
        pass

    # Method to check tap point
    # returns whether a tap lands inside this bubbble
    def contains_point(self, tap_x, tap_y):
        pass

    # Method to find the seconds between spawn time and tap time
    def reaction_time(self, tap_time):
        pass

    # Method to determine if the bubble has outlived its lifetime
    def is_expired(self, current_time):
        pass


class EasyBubbleGame:
    # Constructor for the bubble list, strikes, score, timer and finished/won flags
    def __init__(self, level_number):
        pass

    # Records the start time and spawns the first bubbles
    def start(self, current_time):
        pass

    # Method that is called every frame/tick
    # Expires old bubbles, spawns new bubbles
    # check win/lose conditions
    def update(self, current_time):
        pass

    # Method to create a bubble at a valid position and add it to the list of bubbles
    def spawn_bubble(self, current_time):
        pass

    # Method to take a bubble out of play (popped or expired)
    def remove_bubble(self, bubble_id):
        pass

    # Method to find which bubble (if any) was hit
    # Hit: pop it and award points.
    # Empty Space: add a strike
    def handle_tap(self, tap_x, tap_y, tap_time):
        pass

    # Method to remove the bubble, calculate points, record the reaction time
    def pop_bubble(self, bubble, tap_time):
        pass
    
    # Method to apply the easy-mode equation, then clamp to the min/max range
    def calculate_points(self, reaction_time):
        pass

    # Method to check if the user won
    # returns whether the level was survived or all bubbles were popped
    def check_win(self, current_time):
        pass

    # Method to check if the user lost
    # returns whether the strikes have reached the limit
    def check_loss(self, current_time):
        pass

    # Method to end the level
    # Freezes the game state and computes the final results
    def end_level(self, won):
        pass

    # Method to convert the final score or reaction data into 0-3 stars
    def calculate_stars(self):
        pass

    # Method to get the results of the level
    # returns a summary for the front end: won, sccore, stars, strikes, poppede count
    def get_results(self):
        pass