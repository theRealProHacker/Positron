# Style Invalidation

You probably already know the joke:

> There are 2 truly difficult problems in Computer Science  
> 1. Naming things  
> 2. Cache Invalidation  
> 3. Off by one errors  

Well, we aren't doing cache invalidation per se, but style invalidation which is pretty similar. 
The question is: "How do we know when we need to reapply styling to our elements?". 

Applying styling means taking the global stylesheet, matching all selectors onto the elements and then assigning the resulting style to each element. This is a pretty expensive operation if you have many selectors, complex selectors or just a huge DOM. For that reason we only really want to do it if necessary. And just as a tip it should **not** be necessary in 99% of frames.  
So now let us just look at some reasons when it would be necessary. 

1. A stylesheet is removed. This is definitely a reason, but it happens really, really, really rarely. We hold all stylesheets in a `WeakSet`. If a `StyleElement` is removed from the DOM, it is automatically garbage collected. With this the strong reference to the stylesheets(s) it carried vanishes and the stylesheet is removed from the `WeakSet`. We notice this by also saving the length of that `WeakSet`. If the actual length is smaller than that, then a stylesheet was removed. 
2. Something changed selector matching. This includes:
    1. The media changed (The window was resized)
        ```css
        @media(min-width: 300px) { ... }
        ```
    2. The DOM was manipulated in any way (attrs were changed or elements were added or removed)  
        ```css
        .class { ... }
        ```
    3. A pseudoclass changed (A new element is hovered)
        ```css
        :hover { ... }
        ```
3. A StyleSheet was added. Here, we don't really need to reapply styling using all stylesheets. Instead, we could just merge the added stylesheet into the already existing styles on the elements. So, lets say a p-element has the style
    ```python
    {
        "width": (Auto, False) # The value + plus whether it is important
    }
    ```
    and a new stylesheet is added
    ```css
    p {
        width: 200px !important;
    }
    div {
        ...
    }
    ```
    Then the matching style is 
    ```python
    {
        "width": (Length(200), True)
    }
    ```
    This can be merged into the existing style and just replaces the present definition because it is marked as `!important`. 
    ```python
    {
        "width": (Length(200), True)
    }
    ```
    There is one thing about this and that is that we are not really caring about the order of style elements.
    ```html
    <head>
        <style id="style1"></style>
    </head>
    ```
    If another style is inserted now, our current algorithm doesn't take into consideration whether the style is inserted before or after the first one. In real life this does make a difference. 

The next question is "What Elements do we need to apply restyling to?".  
Let's say we have this html
```html
<div>
    <p>
        <span>Some text</span>
    </p>
</div>
```
and now we add a class `super-style` to the span. Does this really ever effect its parents in any way.    
Not really but sometimes yes. There is only a single selector that can make this happen and that is the `:has` pseudo-selector, the most powerful css-selector. But that is not only in Selectors Level 4, but we also don't implement it yet. Until then we can just stick to only reapplying styling to siblings and children of span. 

So, we need to somehow know which elements should get reapplied styling. But that is a TODO; at least until we can profile our code.


# Add "Listeners"

You could introduce a concept of listening. For example given the following css and html
```html
<div>
    <p></p>
    <p></p>
</div>
```
```css
{
    div.class p {
        ... /*something else*/
    }
}
```
This would add a listener onto all div parents of p elements. The listener listens to their class and includes the css that would be applied. Now when the class of div is set to "class", it sees the listener and applies the style to the p elements instead of reapplying the css to every element. 

Or here 
```html
<a>
<p>
```
```css
{
    a:hover+p {
        ...
    }
}
```
The a would get a listener to its hover state. When it is then hovered, ps style gets updated. 
This listener approach obviously also works on things like `.class`. However, in this case for example this would have to put a listener onto every element.