"""
In this file we will experiment with different layouts.
"""

# Layout is determined by the combination of `display`s

# Flow Layout

## Inline Flow layout
"""
attrs:
line-height
word-wrap
word-spacing
text-align and vertical-align
"""
"""
Pseudo-Code:
Put all elements into lines 
from the elements widths (with word-spacing) and the lines max widths. 
For every line get its top, center, baseline and bottom (with line-height and more). 
Align elements inside lines with text-align. 
Align lines inside the height if given, else don't vertical-align. 
"""

## Flow layout
"""
attrs:
position !
width, height
margin, border, padding
inset (top, right, bottom, left)
"""

"""
Pseudo-Code:
"""

## Float layout
"""
We will not implement Float layout because it 
is redundant with flexbox and grid, but annoying and destructive. 
"""
