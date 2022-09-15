# CSS and Cascading

## How does CSS work?
So at the beginning, the browser doesn't really know of any CSS. Then, when it parses the HTML, it finds a `<link>` or `<style>` tag, which directly or indirectly contains CSS. 

This CSS is then parsed into a list of rules, there are two kinds of rules:
1. `AtRules`, which are kind of special rules that get a special treatment
```css	
@media print {
    
}
// or
@import url("example.css");
```
2. "Normal" `StyleRules`, which start with a selector and have a list of property declarations
```css
:root {
    --main-text-color: #000;
    color: var(--main-text-color) !important;
}
```
I will not go over handling `AtRules` just now but instead skip directly to the `StyleRules`.
To parse a CSS-Style-Sheet I use `tinycss`. The name fits perfectly, it really just does what its supposed to do.
Then I convert the `tinycss`-Sheet into an own format. The code for this is in `Style.py` as is all code for handling CSS.
There you can find the function `parse_sheet`, it takes a str and returns a fresh new `SourceSheet`, which really just is a list of `Rules` that pretends like its hashable. 
In `tinycss` a `StyleRule` is called a `RuleSet`. We then process that `RuleSet` to convert it into something like this
```python
typical_style_rule = (
    selector, {
        "property1": value1,
        "property2": value2,
        "property3": value3,
    }
)
```
But I skipped the most important step, the preprocessing. There are two steps to preprocessing. 
The first step is to unpack shorthands and the second step is to precompute constant variables, lets look into this in more detail.
#### Shorthand unpacking
If the CSS-author specifies that the `margin` should be `2px 1em 0 auto` then that results in the following data:
```python
{
    "margin-top": "2px",
    "margin-right": "1em",
    "margin-bottom": "0",
    "margin-left": "auto",
}
```
#### Precomputing constant variables
Then this data is fed back into the preprocessor `process_property` (look into `process_input` for how this is done (it's pretty simple))
And in this step two things happen, if there is a longhand attribute:
1. Validation
2. Replacing the str with a computed value if possible.

And for this we have a protocol. Every known property has a record called a `StyleAttr` which contains several pieces of information:
1. initial value of the attribute
2. any keywords that are valid for the attribute (For example the width property has the keyword `auto`, which is mapped to `Auto`)
3. an `Acceptor`, which takes a string value and a parent style and either returns a computed value or None or raises a KeyError. 
4. whether the property inherits automatically (the color property for example inherits, but width doesn't)
5. That's it

Every StyleAttr then has a method `accept` which combines the keywords with the acceptor function.

So now we call this `accept` method, if it returns a value, we insert that value, if it returns None, we reject the value and if it raises a KeyError, we just insert the raw string back in. To distinguish between an accepted string and an input string we create a class `CompStr`. For example `process_property("display", "none")->CompStr("none")`
```python
# in is_valid
value: str
with suppress(KeyError):
    return attr.accept(value, p_style={})
return value
# in process_property
assert (new_val := is_valid(key, value)) is not None, "Invalid Value"
return new_val
# in process_input
except AssertionError as e:
    reason = e.args[0] if e.args else "Invalid Property"
    log_error(f"CSS: {reason} ({k}: {v})")
```
So now 
```python
{
    "margin-top": "2px",
    "margin-right": "1em",
    "margin-bottom": "0",
    "margin-left": "auto",
}
```
becomes
```python
{
    "margin-top": Length(1),
    "margin-right": "1em",
    "margin-bottom": Length(0),
    "margin-left": Auto,
}
```
Note how the "1em" is still a string, because it can only be computed when the font-size is known
Lets just assume our style sheet just had this one rule with the `p` selector, then we would have a `SourceSheet` that looks like this after joining back the selector and the `!important` information
```python
SourceSheet(
    [
        (
            TagSelector("p"),
            {
                "margin-top": (Length(1), False),
                "margin-right": ("1em", False),
                "margin-bottom": (Length(0), False),
                "margin-left": (Auto, False),
            }
        )
    ]
)
```
This `SourceSheet` is then saved in a global store as `g["css_sheets"]`. This store is internally a WeakValueDict, which means that if the `StyleElement` that holds the `SourceSheet` is deleted, the `SourceSheet` is automatically also deleted. To notice this we also hold a global variable `g["css_sheet_len"]`.

This setup enables us to check if we need to redistribute css when a `SourceSheet` is deleted or added. We just check if either the length of the `g["css_sheets"]` changed or if the global `g["css_dirty"]` was set (for example when a new `StyleElement` is created).

The code for what happens then is in `Element.apply_style()`. It joins all `SourceSheets` into one and then parses the `Selectors`. 
For every `Element` it applies all the styles with selectors that match the element.
These `Styles` are then joined depending on their importance and applied to the element by setting its `estyle` attribute. 

This is really almost everything, but now we handle what happens in `Element.Element.compute()`.
This method is theoretically called every frame before layout and it's very simple. It takes it's `estyle` and `istyle` (the inline style that is specified as `style="color: red"` and parsed in the exact same way but without the selector obviously)

The only thing that happens in this step is that all values that were left as a real string will be resolved to a computed value definitely. For this the actual parent style is passed and the elements default style is used.  
```python
"div": {
    "display": "block"
}
```
As a result we have a `FullyComputedStyle` which is just a dict with all properties and their computed values. This is then used in the layout and draw step.