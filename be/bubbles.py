# Class for one bubble hitbox
class Bubble:
    # Constructor to store: position, size, spawn time, and is_active flag
    def __init__(self, bubble_id, bubbles, x, y, spawn_time):
        self.bubble_id = 0
        self.x = 0
        self.y = 0
        self.radius = 1
        self.spawn_time = 0
        self.is_active = True
        self.bubbles = []
        pass

    # Method to find the seconds between spawn time and tap time
    def reaction_time(self, tap_time):

        pass

    # Method to determine if the bubble has outlived its lifetime
    def is_expired(self, current_time, level):
        pass

    # Method to create a bubble at a valid position and add it to the list of bubbles
    def spawn_bubble(self, current_time, level):
            
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
