# Usable screen area (default 1920 x 1080, backend takes width/height as inputs)
#   Easy/Medium: 120 px top band reserved for strike counter + timer
#       usable = 1920 * 960 = 1,843,200 px^2
#   Hard: same top band, plus 100 px spike strip on each side
#       usable = 1720 * 960 = 1,651,200 px^2
#
#   
# HARD (random radius in range, cap 15)
#   max r = sqrt(0.75 * 1,651,200 / (15 * 3.14159)) = about 162
#   min r = 162 * 0.5 = 81

HARD_MAX_RADIUS = 162
HARD_MAX_AREA = 82447.888
HARD_MIN_RADIUS = 81
HARD_MIN_AREA = 20611.972