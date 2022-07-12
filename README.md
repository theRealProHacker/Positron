# Simple comments

# Sources (MVPs)
- MDN
- [How Browsers work](https://web.dev/howbrowserswork/)
- [Web Browser Engineering](https://browser.engineering/)
## Single sources
- https://zerox-dg.github.io/blog/2021/09/26/Browser-from-Scratch-Layout/
- https://runebook.dev/en/docs/css/css_flow_layout/block_and_inline_layout_in_normal_flow
- https://www.rexegg.com/regex-boundaries.html
- https://hacks.mozilla.org/2017/08/inside-a-super-fast-css-engine-quantum-css-aka-stylo/

# Thoughts

## Stylesheets

## Stylesheet sources

### Global stylesheets
- User agent stylesheet for each attribute
    - inherited values have a default of inherit, most others auto
    - display: inline
- User stylesheet overrides
- Author stylesheet overrides (--root)

### Specific stylesheets
- User agent stylesheet for element x 
    - div: 
- User stylesheet overrides
- Author stylesheet overrides (element selectors)

### Head Style
- User agent style for the head element (tag: html).
    - background: white
    - color: black
- User style overrides


# Internal Attribute Specifications

These specify the attributes with their types and constraints. Every computed type should comply with this specification. That is essential!

- font-weight: 
    - From: number, "normal", "bold", "lighter", and "bolder"
    - To: float between 1 and 1000
    - Implementation:  
        If the exact weight given is unavailable, then the following rule is used to determine the weight actually rendered:

        If the target weight given is between 400 and 500 inclusive:
        Look for available weights between the target and 500, in ascending order.
        If no match is found, look for available weights less than the target, in descending order.
        If no match is found, look for available weights greater than 500, in ascending order.
        If a weight less than 400 is given, look for available weights less than the target, in descending order. If no match is found, look for available weights greater than the target, in ascending order.
        If a weight greater than 500 is given, look for available weights greater than the target, in ascending order. If no match is found, look for available weights less than the target, in descending order.

- font-family: 
    - From: any string
    - To: same string
    - Implementation: complex; defined in some `get_font` method
- font-size:
    - From: length-percentage, absolute kw, relative kw
    - To: float > 0
- font-style: FontStyle
- color: 
    - From: name, rgb, rgba, hex and more
    - To: pg.Color
- display: string (inline, block, none)
- background-color: Color
- width: 
    - From: "auto" or length-percentage
    - To: Length (>=0) or a keyword or percentage
    - Implementation:  
        instead they fill up their parent element completely while respecting its padding. That's how width: auto works.
- height: Length (>=0) or auto or percentage
- position: 
    - From: keyword
    - To: str
- top: 
    - From: "auto" or length-percentage
    - To: float or auto or percentage
- same for bottom, right and left
- box-sizing: "content-box" or "border-box"
- margin(tbrl): float or auto or percentage
- padding(tbrl): float or auto or percentage
- border-width(tbrl): float or auto
- line-height: float or percentage or normal
- word-spacing: float or percentage or normal

# The Element class

x: Number
y: Number

Have different meanings in diferent contexts
Between layout and draw it is set to the location of the margin-box inside the parents content-box
In draw it becomes the location of the margin-box on the screen

width: Number
height: Number

The dimensions of the margin-box of the element.
