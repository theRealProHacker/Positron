
[![Join the chat at https://gitter.im/Positron-Contributors/community](https://badges.gitter.im/Positron-Contributors/community.svg)](https://gitter.im/Positron-Contributors/community?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge&utm_content=badge)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
![Github CI workflow badge](https://github.com/theRealProHacker/Positron/actions/workflows/run-test.yml/badge.svg)

# Positron

**E**lectron uses **E**CMAScript and **P**ositron uses **P**ython 

# Screen cast

This code
```html
<html>
    <title>
        Hero Banner Example
    </title>
    <style src="example.css"></style>
    <body> 
        <div class="hero-banner">
            <div>
                <h1>
                    A useless hero banner
                </h1>
                <h3>
                    And a subtitle, no one is going to ever read (apart from you)
                </h3>
            </div>
        </div>
        <div class="container">
            <h1>
                Here is the content header
            </h1>
            <p>
                Lorem, ipsum dolor sit amet consectetur adipisicing elit. Dolores ut modi ratione. Mollitia consequuntur voluptatem alias, commodi illum dolore odit voluptas animi ipsum velit quasi, nam necessitatibus provident. Deserunt, impedit!
            </p>
        </div>
    </body>
</html>
```
```css
body {
    background-color: grey;
    height: 100%;
}
.hero-banner {
    background-image: url(https://sitefarm.ucdavis.edu/sites/g/files/dgvnsk511/files/styles/sf_title_banner/public/media/images/lighthouse-pixabay-lumix2004.jpg?h=2ed12e5b&itok=ES3yBdhi);
    width: 100%;
    height: 300px;
}
.hero-banner>div{
    display: block;
    margin: 10% auto;
    font-size: x-large;
    width: 90%;
}
.hero-banner h1{
    color: rgb(75, 73, 73);
}
.container{
    width: auto;
    margin: 20px 30px;
    background-color: blanchedalmond;
    padding: 20px;
}
```
creates this result  

![A Screenshot of the result](https://i.ibb.co/47d9kLy/Screenshot-2022-09-22-201336.png)

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
- https://runebook.dev/en/docs/css/css_flow_layout/block_and_inline_layout_in_normal_flow
- https://hacks.mozilla.org/2017/08/inside-a-super-fast-css-engine-quantum-css-aka-stylo/
- [Parsing](https://html.spec.whatwg.org/multipage/parsing.html)
- [Firefox Source Structure](https://firefox-source-docs.mozilla.org/contributing/directory_structure.html)
- [Gamma Correction](https://blog.johnnovak.net/2016/09/21/what-every-coder-should-know-about-gamma/)

# Thoughts
## General Style Guide
1. There is an inner conflict between confirmacy to the Web Standards and practicality. 
    1. We try to implement everything as close to the standards as possible, 
    2. But we don't implement deprecated features or features that are not implemented by most mainstream browsers.
    3. If the standards are ridiculous in some aspects, we go our own way, unless someone finds a good reason not to. 
    4. We don't implement JavaScript, and we don't need to feel forced to even follow the standards for JavaScript when implementing Python APIs. However, it might still help to look at the JS standards for inspiration.
2. In GUI Applications its all about what the user feels. It doesn't matter if your code takes 10 seconds to run, unless the user feels it. If you run that code synchronously and the application freezes for 10 seconds, the user will feel it. If you run it asynchronously, and put in a loading sign the user will still see that it takes some time, but he won't care because he expects that things need time to load. Please just only write asynchronous code!

## Async
To achieve asynchronous code you need two methods:
1. `asyncio.to_thread` two turn a synchronous function into an asynchronous one
2. `util.create_task` to "fire and forget" a coroutine. You can make it `sync` which just means that before the page loads the task will definitely have finished. Also you can add an onfinished callback. 

## Ideas
- Test on https://acid2.acidtests.org/  
- `tinycss` generates tokens like for example `<Token PERCENTAGE at 5:19 70%>`, we could use these. Right now we throw them away by calling `TokenList.as_css()`  
- Use [aiohttp-client-cache](https://github.com/requests-cache/aiohttp-client-cache)
- animated GIF support (https://yeahexp.com/how-to-insert-animated-gif-into-pygame/)
- `@when` and `@else` in CSS: https://css-tricks.com/proposal-for-css-when/
- Profiling: 
    - https://www.youtube.com/watch?v=m_a0fN48Alw
    - https://pythonspot.com/python-profiling/

## Use less RegEx
Many consider regular expressions to be the best thing if it comes to text processing. 
However, it often makes more sense to use other tools.  
For exampe you could use a `GeneralParser`, which is an easy way to tokenize a string.

# Events
## Mouse Events
- [`click`](https://w3c.github.io/uievents/#click) and [`auxclick`](https://w3c.github.io/uievents/#auxclick):
    - target: The Element clicked (bubbles)
    - pos: the mouse position on the screen
    - mods: An int mask, which mods are pressed
    - button: invalid: 0, left: 1, middle: 2, right: 3, 4 and 5 are special buttons
    - buttons: An int mask which mouse buttons are down
    - detail: Which click this is. The 1st, 2nd, 3rd, ... 
- `mousedown`:
    - target: The Element the mouse was pressed in
    - pos
    - mods
    - buttons
- `mouseup`:
    - target: The Element the mouse was released in
    - pos
    - mods
    - buttons
- `mousemove`:
    - target: The Element the mouse was moved in
    - pos: the new mouse position
    - mods
    - buttons
- `wheel`:
    - target
    - pos
    - mods
    - buttons
    - delta: The x and y delta of the mouse wheel event
- Coming: `mouseleave`/`mouseout` and `mouseenter`/`mouseover`

## Keyboard Events
- keydown:
    - 
- keyup:
    - 

## Window Events and Global Events
Window Events only fire on the html element/the document. So call them by doing `event_manager.on(event, callback)` or `J("html").on(event, callback)`.  
- `online` and `offline` with no attributes
- `resize`: 
    - size = (width,height)
- All other pygame events (except for `WINDOWRESIZED`) lowercased.  
The arguments of the event are copied from pygame, so look into the [documentation](https://www.pygame.org/docs/ref/event.html)

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