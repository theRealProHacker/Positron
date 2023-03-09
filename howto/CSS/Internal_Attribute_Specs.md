
## Internal Attribute Specifications

These specify the attributes with their types and constraints. Every computed type should comply with this specification. That is essential!
> Comment: However, these feel more and more redundant now, because Style.style_attrs defines them pretty well.

- font-weight: 
    - From: number, `normal`, `bold`, `lighter`, and `bolder`
    - To: `Number` between `1` and `1000`
    - Implementation:  
        If the exact weight given is unavailable, then the following rule is used to determine the weight actually rendered:

        If the target weight given is between 400 and 500 inclusive:
        Look for available weights between the target and 500, in ascending order.
        If no match is found, look for available weights less than the target, in descending order.
        If no match is found, look for available weights greater than 500, in ascending order.
        If a weight less than 400 is given, look for available weights less than the target, in descending order. If no match is found, look for available weights greater than the target, in ascending order.
        If a weight greater than 500 is given, look for available weights greater than the target, in ascending order. If no match is found, look for available weights less than the target, in descending order.

- font-family: 
    - From: comma-seperated list of font families, last one can be generic
    - To: tuple of families
- font-size:
    - From: `length-percentage`, absolute kw, relative kw
    - To: `Length` > 0
- font-style: `FontStyle`
- color: 
    - From: name, rgb, rgba, hex and more
    - Parse-Implementation:
        - Generally both `rgba` and `rgb` are the same as are `hsla` and `hsl`. Also it doesn't matter if the values are seperated by commas or spaces. But the comma notation is preferred. The alpha value is handled always. Any "/" is just ignored.
        - `rgb`: rgb(number or percentage, ..., ...)
        - `hls`: hls(number or angle, percentage, percentage)
        - `hwb`: hwb(number or angle, percentage, percentage)
    - Catch: color names use [the pygame colors](https://www.pygame.org/docs/ref/color_list.html) and not [these](https://en.wikipedia.org/wiki/Web_colors)
    - To: `Color`
- display: keyword
- background-color: `Color`
- background-image: `tuple[Drawable, ...]`
- width: 
    - From: `auto` or `length-percentage`
    - To: `Length` or `Auto` or `Percentage` or `BinOp`
- height: `Length` or `Auto` or `Percentage` or `BinOp`
- position: keyword
- top, bottom, right and left: 
    - From: `auto` or `length-percentage`
    - To: `Length` or `Auto` or `Percentage` or `BinOp`
- box-sizing: `content-box` or `border-box`
- margin(tbrl): `Length` or `Auto` or `Percentage` or `BinOp`
- padding(tbrl): `Length` or `Auto` or `Percentage` or `BinOp`
- border-width(tbrl) and outline-width: `Length`
- border-style(tbrl) and outline-style: `CompStr` (https://drafts.csswg.org/css-backgrounds/#border-style)
- border-color(tbrl) and outline-color: `Color`
- border-radius: `Length` or `Percentage` or `BinOp`
- line-height: 
    - From: `number`, `length-percentage`, `normal`
    - To: `Number` or `Length` or `Percentage` or `Auto` or `BinOp`
- word-spacing: 
    - From: `length-percentage`, `normal`
    - To: `Length` or `Percentage` or `Auto` or `BinOp`
- cursor: 
    - From: a keyword
    - To: a pygame.cursors.Cursor
    - TODO: allow comma seperated list of urls where the last element is a keyword. 