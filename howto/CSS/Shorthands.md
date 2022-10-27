# Shorthands

Shorthands have the purpose of writing css-properties as short as possible and hopefully the least redundant.  
Right now we have to shorthand categories.
1. Directional shorthands
2. Smart shorthands (I haven't found a better name yet)

## Directional shorthands

These are shorthands like `margin` or `border-width`.
and they work very simple. You can give 1-4 values and they will be spread out onto the longhands. The order is always the same.
```py
def process_dir(value: list[str]):
    """
    Takes a split direction shorthand and returns the 4 resulting values
    """
    _len = len(value)
    assert _len <= 4, f"Too many values: {len(value)}/4"
    return value + value[1:2] if _len == 3 else value * (4 // _len)
```
So that 
```
x -> [x]*4
x,y -> [x,y,x,y]
x,y,z -> [x,y,z,y] and
x,y,z,w -> [x,y,z,w]
``` 
For most properties the longhands are
```py
directions = ("top", "right", "bottom", "left")
```
corners are
```py
corners = ("top-left", "top-right", "bottom-right", "bottom-left")
```

## Smart shorthands
Example: `outline` splits up into `outline-style`, `outline-color` and `outline-width`. Because these all accept different values, the order doesn't matter. 
The algorithm looks pretty simple.
First split the possible values into a list. Then go through the list and pop the first matching property.
Example:
1. `outline: medium solid blue` gets split into `["medium", "solid", "blue"]` 
2. "medium" doesn't match `style` or `color` but matches `width`. The set of possible values is reduced to `style` and `color`
3. "solid" matches `style`. The set of possible values is reduced to just `color`
4. "blue" matches `color`. Perfect we are done! 😉
```py
# shorthand is the set of accepted longhands
elif (shorthand := smart_shorthands.get(key)) is not None:
    assert len(arr) <= len(
        shorthand
    ), f"Too many values: {len(arr)}, max {len(shorthand)}"
    if len(arr) == 1 and (_global := arr[0]) in global_values:
        return [(k, _global) for k in shorthand]
    _shorthand = shorthand.copy()
    result: list[tuple[str, str]] = []
    for sub_value in arr:
        for k in _shorthand:
            if is_valid(k, sub_value) is not None:
                break
        else:  # no-break
            raise AssertionError(f"Invalid value found in shorthand 'sub_value'")
        _shorthand.remove(k)
        result.append((k, sub_value))
    return result
```

## Very Special Shorthands
Very special shorthands are treated specially. An example is `border-radius` if it contains `/`. 


