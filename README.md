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
    - inherited values have a default of inherit
    - display: "inline"
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
- height: Length (>=0) or Auto or percentage
- position: 
    - From: keyword
    - To: str
- top: 
    - From: "auto" or length-percentage
    - To: float or Auto or percentage
- same for bottom, right and left
- box-sizing: "content-box" or "border-box"
- margin(tbrl): float or Auto or percentage
- padding(tbrl): float or Auto or percentage
- border-width(tbrl): float or Auto
- line-height: float or percentage or Normal
- word-spacing: float or percentage or Normal

# The Element class

box: Box
display: str

compute:
    https://developer.mozilla.org/en-US/docs/Web/CSS/computed_value
    The computed value of a CSS property is the value that is transferred from parent to child during inheritance. 
    It is calculated from the specified value by:

    1. Handling the special values inherit, initial, revert, revert-layer, and unset.
    2. Doing the computation needed to reach the value described in the "Computed value" line in the property's definition table.

    The computation needed to reach a property's computed value typically involves converting relative values 
    (such as those in em units or percentages) to absolute values. 
    For example, if an element has specified values font-size: 16px and padding-top: 2em, 
    then the computed value of padding-top is 32px (double the font size).

    However, for some properties (those where percentages are relative to something that may require layout to determine, 
    such as width, margin-right, text-indent, and top), percentage-specified values turn into percentage-computed values. 
    Additionally, unitless numbers specified on the line-height property become the computed value, as specified. 
    The relative values that remain in the computed value become absolute when the used value is determined.
