
[![Join the chat at https://gitter.im/Positron-Contributors/community](https://badges.gitter.im/Positron-Contributors/community.svg)](https://gitter.im/Positron-Contributors/community?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge&utm_content=badge)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
![Github CI workflow badge](https://github.com/theRealProHacker/Positron/actions/workflows/run-test.yml/badge.svg)

# Positron

**E**lectron uses **E**CMAScript and **P**ositron uses **P**ython 

# How to run this
You need Python 3.10 and Git installed
```shell
git clone https://github.com/theRealProHacker/Positron.git
cd Positron
python3 -m venv venv
venv\Scripts\activate   &:: on Windows
venv/bin/activate       # on Unix 
pip install -r requirements.txt
```
Now you can create an HTML-file `example.html` and then you just do  
```shell
python3 main.py
```

# Sources 
## MVPs
- [MDN](developer.mozilla.org)
- [The official HTML specifications](html.spec.whatwg.org)
- [How Browsers work](https://web.dev/howbrowserswork/)
- [Web Browser Engineering](https://browser.engineering/)
- Just to be honest [StackOverflow](https://stackoverflow.com)
## Single sources
- https://zerox-dg.github.io/blog/2021/09/26/Browser-from-Scratch-Layout/
- https://runebook.dev/en/docs/css/css_flow_layout/block_and_inline_layout_in_normal_flow
- https://hacks.mozilla.org/2017/08/inside-a-super-fast-css-engine-quantum-css-aka-stylo/
- [Parsing](https://html.spec.whatwg.org/multipage/parsing.html)
- [Firefox Source Structure](https://firefox-source-docs.mozilla.org/contributing/directory_structure.html)
- [Gamma Correction](https://blog.johnnovak.net/2016/09/21/what-every-coder-should-know-about-gamma/)

# Thoughts
Test on https://acid2.acidtests.org/  
`tinycss` generates tokens like for example `<Token PERCENTAGE at 5:19 70%>`, we could use these instead of throwing them away by calling `TokenList.as_css()`
## Use less RegEx
Many consider regular expressions to be the best thing if it comes to text processing. 
However, it often makes more sense to use other tools like `str.removesuffix()` or `str.split()`/`re.split()`.  
Or use a `GeneralParser` which is an easy way to tokenize a string.
## Feature Ideas
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
5. URLs can generally also be absolute or relative paths. `file`-URLs are not accepted

# Rants
## Why Python is definitely better then JS
From https://stackoverflow.com/a/2346626/15046005
> technically javascript to python would be a decompiler

## Why the CSS-Specifications are pretty bad
1. Many Inconsistencies. Very similar concepts have totally different syntaxes. 
    Simple example: `rgb` and `hwb`  
2. Sometimes the specifications were done respecting the implementors but then somewhere else they don't care about those at all and then you see CSS-'Features' that are not supported by a single browser.
3. Because CSS was sometimes tailored to very old hardware or other almost ancient circumstances, it has a lot of technical debt. Another reason for this is that just like HTML and JS, CSS cannot have breaking changes, even if totally necessary. 
For example there are a million ways to say the same thing in CSS (colors, tranparency)
4. But in general, CSS is a simple and effective language to describe how a webpage should look like. 
5. Additionally, Positron has an advantage because it firstly doesn't need to support every feature or every device, currently. And secondly, anyone designing a desktop app with it doesn't need to care about supporting IE7 or similar, in contrast to some actual web-developers. 

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

