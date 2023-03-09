# Selectors

CSS-Selectors are frankly pretty amazing. They allow us to assign elements different styles depending on different characteristics elements have or depending on the constellation that elements are in.

The currently supported `Selector`s can be viewed in [Selector.py](../../Selector.py). 

Selector-Matching is the process of either checking whether a single `Element` matches a `Selector`. Or more commonly it means finding all `Element`s in the DOM, or a part of it, that match the selector. A very simple algorithm just goes through every `Element` and matches it against the selector. That finds you all the matching `Element`s for sure, but it is pretty slow. It scales at least linear or even faster with complex selectors. That is pretty bad, if you have a lot of `Element`s. What we really want to achieve is a runtime of O(1). That is of course not easy, but it is worth it. Especially, the most common selectors should be made fast. For that reason most browsers have a hashmap (dict in python) for at least id and class and maybe also tags. 

So this could look like this

```python
# you could make this a WeakSet so that Elements automatically get removed when they are deleted
id_map = defaultdict(set) 

class Element:
    def __init__(self):
        ...
        if (id_:=self.attrs.get("id")):
            id_map[id_].add(self)
        ...
```

Now matching the `IdSelector` onto the DOM is pretty simple:
```python
@dataclass
class IdSelector:
    id: str

def find_all(selector):
    if isinstance(selector, IdSelector):
        return id_map[selector.id]
```

The cool thing about `set`s is that they have common operations like union and intersection. A `union` is basically just an `or` and an `intersection` is just like an `and`. 

```python
def find_all_in(elem, selector):
    return find_all(selector).intersection(elem.all_children)
```

And this obviously also helps us with other selectors like the `AndSelector`

```python
def find_all(selector):
    if isinstance(selector, AndSelector):
        # in reality the AndSelector has an unlimited amount of selectors
        sel1, sel2 = AndSelector.selectors
        return find_all(sel1) & find_all(sel2)
```

If we have `a.button` for example that will find us all elements that have the tag `a` (O(1)) then it will find all the elements that have the class `button` (O(1)) and then it will find us the intersection of these `O(n)`. You might argue that that is still linear. But the n here is the max of the number of items that are links and that have the class button attached. That is significantly smaller than n, the number of all elements in the entire DOM. Really, what we reached here is smallest n we can get to. We could really not do much more optimization but trying to get to the smaller number of compares. 

# No map?
`a[href]` matches all `AnchorElement`s that have a `href` attribute. There is no map keeping track of all elements with an `href` attribute. 

In our first attempt, we would go through every element and check if it has both the tag `a` and also an attribute of `href`.  
In our second attempt, we would get a set of `a` Elements and a set of `[href]` Elements and then just get the intersection. But that might be even worse than the first attempt.  
So in the third attempt, we get all `a` Elements and then check if any of these have the `href` attribute. This is the most human approach and probably also the best.

# Order selectors
We need to somehow know which selectors to get first and for that we need to order them. For example
1. id
2. class
3. tag
4. anything else

`a.button[href]` should for example get all `.button`s and then return all of those that also have the `a` tag and the `href` attribute (We don't need to access the tag map anymore).

If the selector has multiple high "value" selectors it uses the intersection. 
`a.button.heart[href]` should get the intersection of `.button`s and `.heart`s and then procede as above. 

Also if the selector only has rank-4 subselectors then we still use our old method of going through all elements.  

# Relative Selectors
Relative Selectors are selectors that refer to the relationship between elements. Like a child, a descendant, a predecessor or whatever. An example is `.row>.column`. These should be read from right to left. It matches all elements that are `.columns` and that have a direct `.row` parent. A human would probably just look at all rows and then check if their children are of class `column` or you could take the intersection of all direct children of `.row`s and all `.columns`. 

But then we also need to look at a lot of other scenarios to find a solid algorithm that finds the best ways to match selectors.
`#navbar ul a.navlink` matches all navlink anchors that are somwhere in an unordered list that is somewhere in the navbar. 

We could look at every element and check whether it matches `a.navlink` and has a parent that matches `#navbar ul`. Which means checking whether any parent matches `ul` and has any parent that matches `#navbar`. That is disgusting!

Instead what we really want is.
1. Get all `#navbar`s (probably just 1)
2. Get all `ul`s in the DOM (O(1)) and intersect them with all of the navbars children
3. Get all children of any element in that intersection and intersect that with all Elements that are `.navlinks`s and also are `a`s. That last step we took from the `AndSelector` algorithm we discussed earlier. 

Here again we use ordering. We start with the #navbar because it's an `IdSelector` and then we just go down from there (or up if the selector looked like this for example `body #navbar ul a.navlink`).

If you master all of these difficulties you will eventually get faster Selector matching. 

Until someone comes with `* * * * * * * * * * * * * *` (all Elements at least 14 levels deep) or something similarly disturbing. 

# [Pseudoclasses](https://drafts.csswg.org/selectors/#pseudo-classes)

Pseudoclasses are classes of the form `:pseudoclass` and they are currently implemented followingly:

The selector `StateSelector("pseudoclass")` matches exactly all elements that have an attribute `pseudoclass` that is also set to True. `-` is replaced with `_` as almost always when converting identifiers from css to Python. 

So called functional pseudoclasses are not supported yet. They look like a regular css function prepended with a `:`.
Examples are `nth-child` or `is`. 

Instead of having `nth-last-child(x)` in this pythonic environment you should write `nth-child(-x)`.  
`nth-child(0)` never matches/is invalid