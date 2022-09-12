# Simple comments

[![Join the chat at https://gitter.im/Positron-Contributors/community](https://badges.gitter.im/Positron-Contributors/community.svg)](https://gitter.im/Positron-Contributors/community?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge&utm_content=badge)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

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
Somehow move `Selectors` out of `Element` because they don't really belong there
## Use less RegEx
Many consider regular expressions to be the best thing if it comes to text processing. 
However, it often makes more sense to use other tools like `str.removesuffix()` or `str.split()`/`re.split()`  
Or use a `GeneralParser` that is an easy way to tokenize a string.
## Feature Ideas
- https://web.archive.org/web/20110210133151/http://refactormycode.com/codes/333-sanitize-html
- animated GIF support (https://yeahexp.com/how-to-insert-animated-gif-into-pygame/)
- `@when` and `@else` in CSS: https://css-tricks.com/proposal-for-css-when/

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

## Over view of CSS Realms (Specs)
1. Value Calculation, Cascading, CSSOM (How does style get to an element)
    - https://www.w3.org/TR/css-cascade-3/
        - https://www.w3.org/TR/css-cascade-4/
        - https://www.w3.org/TR/css-cascade-5/
        - https://www.w3.org/TR/css-cascade-6/
    - http://www.w3.org/TR/css-variables/
    - https://www.w3.org/TR/css-values-3/
        - https://www.w3.org/TR/css-values-4/
    - www.w3.org/TR/css3-conditional/
        - https://www.w3.org/TR/mediaqueries-3/
        - https://www.w3.org/TR/mediaqueries-4/
    - https://www.w3.org/TR/selectors-4/
    - https://www.w3.org/TR/cssom/
        - https://www.w3.org/TR/cssom-view/
    
2. Layout and Boxes
    - https://www.w3.org/TR/css3-layout/
    - https://www.w3.org/TR/css-inline-3/
    - https://www.w3.org/TR/css-box-3/
    - http://www.w3.org/TR/css-sizing-3/
        - http://www.w3.org/TR/css-sizing-4/
    - http://www.w3.org/TR/css-display-3/
    - http://www.w3.org/TR/css-overflow-3/
        - http://www.w3.org/TR/css-overflow-4/
    - https://www.w3.org/TR/css-align-3/
    - https://www.w3.org/TR/css-flexbox-1/
    - https://www.w3.org/TR/css-grid-1/
        - https://www.w3.org/TR/css-grid-2/
        - https://www.w3.org/TR/css-line-grid-1/
    - https://www.w3.org/TR/css-page-floats-3/
        - http://www.w3.org/TR/css3-exclusions/
    - https://www.w3.org/TR/css-content-3/
        - https://www.w3.org/TR/css-pseudo-4/
    - https://www.w3.org/TR/css-lists-3/
        - http://www.w3.org/TR/css-counter-styles-3/
    - https://www.w3.org/TR/css-position-3/
    - https://www.w3.org/TR/css-ruby-1/ ??
3. Fonts and Text
    - https://www.w3.org/TR/css-text-3/
        - http://www.w3.org/TR/css-text-4/
    - https://www.w3.org/TR/css-writing-modes-3/
        - https://www.w3.org/TR/css-writing-modes-4/
    - https://www.w3.org/TR/css-fonts-3/
        - https://www.w3.org/TR/css-fonts-4/
        - https://www.w3.org/TR/css-fonts-5/
        - http://www.w3.org/TR/css-font-loading-3/
    - http://www.w3.org/TR/css-text-decor-3/
        - https://www.w3.org/TR/css-text-decor-4/
4. Colors
    - https://www.w3.org/TR/css-color-3/
        - https://www.w3.org/TR/css-color-4/
5. Animations
    - https://www.w3.org/TR/css-transitions-1/
    - https://www.w3.org/TR/css-animations-1/
        - https://www.w3.org/TR/web-animations-1/
    - https://www.w3.org/TR/css-easing-1/
6. Media
    - https://www.w3.org/TR/css-backgrounds-3/
    - https://www.w3.org/TR/css-images-3/
        - https://www.w3.org/TR/css-images-4/

7. Transforms, filters and other special effects
    - https://www.w3.org/TR/css-transforms-1/
    - https://www.w3.org/TR/css-shapes-1/
    - https://www.w3.org/TR/css-ui-3/
    - https://www.w3.org/TR/css3-hyperlinks/
    - http://www.w3.org/TR/compositing/
    - http://www.w3.org/TR/css-masking/
8. Speech and Aural layout
    - https://www.w3.org/TR/css-speech-1/
9. SVG
10. Parsing and Syntax
    - https://www.w3.org/TR/css-syntax-3/
    - https://www.w3.org/TR/css-style-attr/
## CSS Life Cycle

1. First the css sits as a string in either a css file or in a style tag (or in a style attribute but that is a different thing)
2. Then the css becomes a list of Rules (a SourceSheets).
    - A `Rule` can either be a `StyleRule` or an `AtRule`
    - A `StyleRule` has a selector which corresponds to a `Style`.
    - A `Style` is a dict of key value pairs where the key is the property name 
    and the value is either a pre-computed value or a str
    - This style is the same style that is used in the inline style attribute of an `Element`
3. Then when css becomes dirty through addition or deletion of `SourceSheets` or the change of Media the css is redistributed.
This means that all `AtRules` that couldn't be resolved are resolved 
so that a `SourceSheet` resolves to a list of `Selector-Style` pairs.
4. These Rules are applied to every `Element` by overwriting its `e(xternal)style` attribute. 
The Styles are now resolved and don't include the important information anymore. 
5. All elements are recomputed. In this step the elements compute all uncomputed properties 
and then set their `c(omputed)style` attribute to a `FullyComputedStyle`. In this style, all values definitely comply with the Specifications below. That style is also cached inside a `FrozenDCache` for style sharing. 
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
    - From: anything
    - To: CompStr
    - Implementation: complex; defined in some `get_font` method
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

## Documented differences to the specifications

1. Numbers in CSS can be written with a trailing `.`  
Example: `line-height: 1.`
3. `margin: 0 0 inherit inherit` is also valid and maps to 
```css
margin-top: 0;
margin-left:0;
margin-bottom: inherit;
margin-right: inherit;
```
4. Also if any of the four values in `margin` were invalid, the rest would still be accepted.
5. URLs can generally also be absolute or relative paths without having to use the `file://` syntax

# Rants
## Why Python is definitely better then JS
From https://stackoverflow.com/a/2346626/15046005
> technically javascript to python would be a decompiler

## Why the CSS-Specifications are pretty bad
1. Many Inconsistencies. Very similar concepts have totally different syntaxes. 
    Simple example: `rgb` and `hwb`  
2. Sometimes the specifications were done respecting the actual implementation but then somewhere else they don't care about those at all and then you see CSS-'Features' that are not supported by a single browser.
3. Because CSS was sometimes tailored to very old hardware or other almost ancient circumstances, it has a lot of technical debt. Another reason for this is that just like HTML and JS, CSS cannot have breaking changes, even if totally necessary. 
For example there are a million ways to say the same thing in CSS (colors, tranparency)
4. But in general, CSS is a simple and effective language to describe how a webpage should look like. 
5. Also, Positron has an advantage because it firstly doesn't need to support every feature or every device, currently. And secondly, anyone designing a desktop app with it doesn't need to care about supporting IE7 or similar, in contrast to some actual web-developers. 

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

