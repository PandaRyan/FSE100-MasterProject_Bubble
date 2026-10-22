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

# Static/Final Variables
# Area of each bubble in easy mode will be about 200,000 pixels or 1/10 of the screen
# So r = sqrt (200,000 / 3.14159), after some rounding, the radius is approximately 250 pixels
# using our estimated r to solve for our area, it would be an area of 196,349.375 pixels
RADIUS = 250
AREA = 196349.375

class EasyBubbleGame:
    # Constructor for the bubble list, strikes, score, timer and finished/won flags
    # bubble list will be a list of tuples (bubble_id, )
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