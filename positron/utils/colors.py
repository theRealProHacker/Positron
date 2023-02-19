from own_types import Color
from util import in_bounds


############################# Colors #####################################
def hsl2rgb(hue: float, sat: float, light: float):
    """
    hue in [0,360]
    sat,light in [0,1]
    """
    hue %= 360
    sat = in_bounds(sat, 0, 1)
    light = in_bounds(light, 0, 1)
    # algorithm from https://www.w3.org/TR/css-color-3/#hsl-color
    def hue2rgb(n):
        k = (n + hue / 30) % 12
        a = sat * min(light, 1 - light)
        return light - a * max(-1, min(k - 3, 9 - k, 1))

    return Color(*(int(x * 255) for x in (hue2rgb(0), hue2rgb(8), hue2rgb(4))))


def hwb2rgb(h: float, w: float, b: float):
    """
    h in [0,360]
    w,b in [0,1]
    """
    h %= 360
    if (sum_ := (w + b)) > 1:
        w /= sum_
        b /= sum_

    rgb = hsl2rgb(h, 1, 0.5)

    return Color(*(round(x * (1 - w - b) + 255 * w) for x in rgb))


# TODO: lab, lch, oklab, oklch, etc. to rgb


##########################################################################
