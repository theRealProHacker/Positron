# The CSS-Box-Model

CSS is very simple: **Everything** is a box (a rectangle).  
And every box has different properties. Here we will cover the most common:

1. Metaproperties (Properties that change how the box is lay out)
    - `display`
    - `position`
    - `float`
    - `z-index`

2. Non-Metaproperties
    - `box-sizing`
    - `width`
    - `height`
    - `margin`
    - `padding`
    - `border-width`

What doesn't really belong here is anything only relevant to drawing, like `border-radius` or `outline`

Positron handles these box-properties in a very simple way:

Metaproperties are directly attached to the element, while non-metaproperties are attached in the form of a `Box`.  
This `Box` can be found in `Box.py` and it comes with a lot of helpers but most notably `make_box` which basically creates a `Box` from an `Element`. 

Here I will cover in great detail my thoughts when creating and using this.

# What is a `Box` for?

A `Box` should be able to represent both the source as well as the use cases.  
I noticed that really the use cases are getting three different boxes and their properties:
1. content-box (padding-box): The box inside of the element (where its content comes inside)
2. border-box: The box that the element has render control over in most cases
3. outer-box (margin-box): The space the box takes viewed from the outside. 

So now just assume an element has a `FullyComputedStyle` and wants to get a `Box`, then it calls the `make_box` function.  
Lets look into some code

So here we see that the function takes a lot of stuff. The given width is basically the width the element has to work with. The style is the `FullyComputedStyle` of the element. The parent width and height are the width and height of the element's parent.  
To no surprise it returns a Box, but it also returns a callback-function. This function is for setting the height of the box afterwards if it was set to `Auto`. In that case the height of an element can only be determined after all its children were layouted. The element should call the callback as soon as it knows its height, if the height was `Auto` it is replaced with that new height, else the callback just does nothing. 
```python	
def make_box(
    given_width: float,
    style: FullyComputedStyle,
    parent_width: float,
    parent_height: float,
) -> tuple[Box, Callable[[float], None]]:
```
The next step is setting up the calculator with the parent's width as the default value percentages refer, to getting the `box-sizing`, and then resolving all `padding` or `border` values to floats. The border is always a `Length` and cannot be a `Percentage` or `Auto`, padding can be anything basically. 
```python
    calc = Calculator(parent_width)
    box_sizing: str = style["box-sizing"]

    padding = calc.multi4(pad_getter(style), 0)
    border = calc.multi4(
        bw_getter(style), None, None
    )
```  
The width and margin are a bit special: When they are set to `auto`, they basically take up all available space. A cool feature is that space is always evenly distributed to both sides of the margin (implemented in `merge_horizontal_margin`). So, setting the horizontal margin to `auto` (and setting the width not to `Auto`) can easily center a div in it's parent's content-box. Unlike all the other properties, `Percentages` on height refer to the parent's height. 
> Unfortunately, there is a bug in mypy that makes `tuple[x]()[slice()]` have a type of `x` when really it should be of type `tuple[x, ...]`. There are several issues open on this on GitHub. Just search for `tuple` and `slice`
```python
    if style["width"] is Auto:
        margin = calc.multi4(mrg_getter(style), 0)
        width = given_width
    else:
        # width is a resolvable value. So this time margin: auto resolves to all of the remaining space
        width = calc(style["width"])
        _margin = mrg_getter(style)
        mrg_t, mrg_b = calc.multi2(_margin[_vertical], 0)  # type: ignore
        mrg_r, mrg_l = merge_horizontal_margin(
            _margin[_horizontal],  # type: ignore
            avail=given_width
            - _sum(width, *border[_horizontal], *padding[_horizontal]),  # type: ignore
        )
        margin = mrg_t, mrg_r, mrg_b, mrg_l

    # -1 is a sentinel value to say that the height hasn't yet been specified (height: auto)
    height = calc(style["height"], auto_val=-1, perc_val=parent_height)
```
Here the return values are instantiated, and then returned.  
As explained before, the callback is either the box's `set_height()` or just `noop()`. 
```python
    box = Box(
        box_sizing,
        margin,
        border,
        padding,
        width,
        height,
        outer_width=style["width"] is Auto,
    )
    set_height: Callable[[float], None] = box.set_height if height == -1 else noop
    return (
        box,
        set_height,
    )
```

The `outer_width` keyword argument to the `Box` will be explained just now.  
But first we need to understand box conversion. Basically, we want to be able to convert between different box-types like a content-box and an outer-box. The `box-sizing` property defines which box-type the css width and height refer to (It can only be border-box or content-box).  
As an example when a box with `boxsizing: border-box` gets a width of `100` then the content-box's width is `100-padding[_horizontal]-border[_horizontal]`, which could be pretty small in some circumstances.  

The `Box` just knows it's own box-sizing and its source values and then converts them to the requested box-type on the fly. 
So if we set `outer_width` to `True`, we mean that the width we are referring to is in the `outer-box` box-type and should be automatically converted into the right type. This is because the box's width is just the given width. 

The `Box` module has utility for converting between box-types.  
```python
between_types = [("border", "padding"), ("margin",)]
box_types = [
    "content-box",
    "border-box",
    "outer-box",
]
```
You have to read these as interleaving, a bit like this:
```t
"content-box"<-("border", "padding")->"border-box"<-("margin",)->"outer-box"
```
Between "content" and "border", there is `border` and `padding`, between "border" and "outer" there is `margin`

This data is used by `_convert()`. It takes the `Box`, and the box-types that should be converted between, as well as the part of a value that should be converted. `width` has the `_horizontal` slice for example. From this we know that we should only use that part of `padding`, `border` and `margin`. 
```python
def _convert(box: "Box", frm: str, to: str, part: Index) -> float:
    if frm == to:
        return 0
    _frm = box_types.index(frm)
    _to = box_types.index(to)
    if _frm > _to:  # we are converting from a larger box to a smaller box
        return -_convert(box, to, frm, part)
    lookup_chain = [*chain(*between_types[_frm:_to])]
    return sum(_sum(getattr(box, name)[part]) for name in lookup_chain)
```
To understand the code better, we go through an example:
We are converting from content-box to border-box and the part is `vertical`.
1. `frm != to`
2. `_frm = 0` and `_to = 1` -> `frm < _to`
3. The `lookup_chain` is created by chaining all space between these box-types. In this case it is the chain of `[("border", "padding")`. Which means that `border` and `padding` are the difference when converting from content-box to border-box. But we only take the vertical part of these and just sum them all up. 
This sum is returned. If it is negative that means we converted from a larger box-type to a smaller box-type.  

The `convert` method just wraps this function and flips it's sign depending on whether we are manipulating the position or the size of a box. Also a size can never be negative. 

A `Box` has lots of utilites. For example we have a Sentinel-Box `<EmptyBox>` or `Box.empty()` and many nice extras for manipulating boxes just like your heart desires. 