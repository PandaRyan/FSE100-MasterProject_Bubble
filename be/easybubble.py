from bubbles import Bubble

# This will be the class for the easy mode:
#   Tap a bubble to pop it. 
#   3 X's = lose
#   Survive 60 seconds to win

# Constraints:
#   LEVEL_DURATION, MAX_STRIKES, BUBBLE_LIFETIME
#   SCORE_SLOPE, SLOPE_INTERCEPT (obtained from the star files equations)
#   MAX_POINTS_PER_BUBBLE, MIN_POINTS_PER_BUBBLE
#   STAR_THRESHOLDS (what earns 1, 2, or 3 stars)

# Usable screen area (default 1920 x 1080, backend takes width/height as inputs)
#   Easy/Medium: 120 px top band reserved for strike counter + timer
#       usable = 1920 * 960 = 1,843,200 px^2
#   Hard: same top band, plus 100 px spike strip on each side
#       usable = 1720 * 960 = 1,651,200 px^2
#
# Radius formula: r = sqrt(coverage * usable_area / (max_bubbles * 3.14159))
# Coverage is worst case: every bubble at the cap is the largest radius, at 75%
# Min radius for medium/hard is 50% of the max radius, rounded

# EASY (fixed size, cap 10)
#   r = sqrt(0.75 * 1,843,200 / (10 * 3.14159)) = about 210
EASY_RADIUS = 210
EASY_AREA = 138544.119


class EasyBubbleGame:
    # Constructor for the bubble list, strikes, score, timer and finished/won flags
    # bubble list will be a list of tuples (bubble_id, x, y, spawn_time)
    def __init__(self):
        self.bubble_list = []
        self.strikes = 0
        self.score = 0
        self.start_time = 0
        self.end_time = 0
        self.finished = False
        pass

    # Records the start time and spawns the first bubbles
    def start(self, current_time):
        self.start_time = current_time
        
        pass

    # Method that is called every frame/tick
    # Expires old bubbles, spawns new bubbles
    # check win/lose conditions
    def update(self, current_time):
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