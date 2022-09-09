# Simple comments

# Sources (MVPs)
- [MDN](developer.mozilla.org)
- [The official HTML specifications](html.spec.whatwg.org)
- [How Browsers work](https://web.dev/howbrowserswork/)
- [Web Browser Engineering](https://browser.engineering/)
- Just to be honest [StackOverflow](https://stackoverflow.com)
## Single sources
- https://zerox-dg.github.io/blog/2021/09/26/Browser-from-Scratch-Layout/
- https://runebook.dev/en/docs/css/css_flow_layout/block_and_inline_layout_in_normal_flow
- https://www.rexegg.com/regex-boundaries.html
- https://hacks.mozilla.org/2017/08/inside-a-super-fast-css-engine-quantum-css-aka-stylo/

## Sites to save
- [Parsing](https://html.spec.whatwg.org/multipage/parsing.html#tokenization)
- [Firefox Source Structure](https://firefox-source-docs.mozilla.org/contributing/directory_structure.html)

# Thoughts
## Use less RegEx
Many consider regular expressions to be the best thing if it comes to text processing. 
However, it often makes more sense to use other tools like `str.removesuffix()` or `str.split()`/`re.split()`
## Feature Ideas
- https://web.archive.org/web/20110210133151/http://refactormycode.com/codes/333-sanitize-html
- animated GIF support (https://yeahexp.com/how-to-insert-animated-gif-into-pygame/)

## Problems that this project is currently facing
1. Unicode and font selection
2. Fast media (images, videos, audio). This applies especially to video. Which is basically moving image synced with audio
3. Using the GPU to accelerate drawing. (Related to 2.)
4. Support for all formats (eg. animated GIF)

# Stylesheets

## Global stylesheets
- User agent stylesheet for each attribute
    - inherited values have a default of inherit
    - others have other default values:  
    `display: "inline"`
- User stylesheet overrides

## Specific stylesheets
- User agent stylesheet for element x  
    https://www.w3.org/TR/CSS2/sample.html  
    https://trac.webkit.org/browser/trunk/Source/WebCore/css/html.css  
    https://hg.mozilla.org/mozilla-central/file/tip/layout/style/res/html.css  
    https://www.w3schools.com/cssref/css_default_values.asp  
    Example  
    ```css
    div {
        display: "block"
    }
    ```
- User stylesheet overrides
- Author stylesheet overrides (element selectors)

# CSS

## CSS Life Cycle

1. First the css sits as a string in either a css file or in a style tag (or in a style attribute but that is a different thing)
2. Then the css becomes a list of Rules (a SourceSheets).
    - A Rule can either be a StyleRule or an AtRule
    - A StyleRule has a selector which corresponds to a Style.
    - A Style is a dict of key value pairs where the key is the property name 
    and the value is either a pre-computed value or a str
    - This style is the same style that is used in the inline style attribute of an Element
3. Then when css becomes dirty through addition or deletion of SourceSheets or the change of Media the css is redistributed.
This means that all AtRules that couldn't be resolved are resolved 
so that a SourceSheet resolves to a list of Selector-Style pairs.
4. These Rules are applied to every Element by overwriting its e(xternal)style attribute. 
The Styles are now resolved and don't include the important information anymore. 
5. All elements are recomputed. In this step the elements compute all uncomputed properties 
and then set their c(omputed)style attribute to a `FullyComputedStyle`. In this style, all values definitely comply with the Specifications below. That style is also cached inside a `FrozenDCache` for style sharing. 
6. The elements can now use their computed style to layout and draw themselves and their surrounding elements.


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
    - From: any string
    - To: same string
    - Implementation: complex; defined in some `get_font` method
- font-size:
    - From: `length-percentage`, absolute kw, relative kw
    - To: `Length` > 0
- font-style: `FontStyle`
- color: 
    - From: name, rgb, rgba, hex and more
    - To: `Color`
- display: keyword
- background-color: `Color`
- background-image: `tuple[Drawable, ...]`
- width: 
    - From: `auto` or `length-percentage`
    - To: `Length` (>=0) or `Auto` or `Percentage`
- height: `Length` (>=0) or `Auto` or `Percentage`
- position: keyword
- top, bottom, right and left: 
    - From: `auto` or `length-percentage`
    - To: `Length` or `Auto` or `Percentage`
- box-sizing: `content-box` or `border-box`
- margin(tbrl): `Length` or `Auto` or `Percentage`
- padding(tbrl): `Length` or `Auto` or `Percentage`
- border-width(tbrl): `int`
- border-style(tbrl): `str` (https://drafts.csswg.org/css-backgrounds/#border-style)
- border-color(tbrl): `Color`
- border-radius: `Length` or `Percentage`
- line-height: `Number` or `Length` or `Percentage` or `Normal`
- word-spacing: `Number` or `Percentage` or `Normal`

## Documented differences to the specifications

1. Numbers in CSS can be written with a trailing `.`  
Example: `line-height: 12.` (Please don't do this)
3. `margin: 0 0 inherit inherit` is also valid and maps to 
```css
margin-top: 0;
margin-left:0;
margin-bottom: inherit;
margin-right: inherit;
```
4. Also if any of the four values in `margin` were invalid, the rest would still be accepted.
5. URLs can generally also be absolute or relative paths without having to use the `file://` syntax


# Why Python is definitely better then JS
From https://stackoverflow.com/a/2346626/15046005
> technically javascript to python would be a decompiler


# The Element class

box: Box  
display: str

[compute](https://developer.mozilla.org/en-US/docs/Web/CSS/computed_value):  

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

