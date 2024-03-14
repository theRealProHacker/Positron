# How does the DOM work in Positron?

DOM is short for "Document Object Model" and really is just a fancy word for a collection of HTML-Elements in a tree structure.  
Every `Element` has a parent (except for the tree root) and a number of children, also every `Element` has a tag, and some attributes. Text is represented as a `TextElement`. 

Most of the CSS handling is discussed in [CSS/Overview](CSS/Overwiew.md) and `Box`es are discussed in [CSS/Box](CSS/Box.md). From the `Element`s style attribute, we get the inline style, also external style is applied to any `Element` from outside. Every `Element` has a compute method, which takes the styles, fuses them and then computes them, which just means that it uses it's parent's style to resolve all unresolved values. 

Also an `Element` has special attributes related to drawing but mostly layout. The most important are the combination of display and layout_type. `display` says how the element displays itself, `layout_type` says how the element displays its children. The body-Element below has a `display` and `layout_type` of `block`. The p-Element has a `display` of `block` and a `layout_type` of `inline` and the span has a `display` and `layout_type` of `inline`. 

```html
<body>
    <p>
        <span>Some inline content</span>
        Even more inline
    </p>
<body>
```

## The Element Definition 
> Note: This is pretty likely outdated when you read this and has no ambition to be complete, so look it up yourself in Element.py
```python
# General
tag: str
attrs: dict[str, str]
children: list[Union["Element", "TextElement"]]
real_children: list["Element"] # no MetaElements
parent: Optional["Element"]
text: str
# Style
istyle: Style.Style  # inline style
estyle: Style.Style  # external style
cstyle: Style.FullyComputedStyle  # computed_style
input_style: Style.ResolvedStyle  # the combined input style
# Layout + Draw
box: Box.Box
line_height: float
white_spacing: float
display: DisplayType
layout_type: DisplayType
position: str

# Dynamic states
active: bool = False
focus: bool = False
hover: bool = False

```

In normal browsers the DOM is not used for layouting or drawing directly. Instead every DOM-Node creates any number of layout boxes. These layout boxese are the used for layouting and drawing. We instead use the DOM directly.

Elements that don't want to draw themselves, can just not draw themselves. Equally, Elements that are scrollable don't need to create a scrollbox and put their children inside. Instead any element is scrollable that has some kind of scroll attributes (like for example scroll_pos). That Element then just draws itself and it's children accordingly and then also draws the scroll bar. This is an important concept to keep in mind. 