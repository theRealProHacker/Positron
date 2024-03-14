[![Join the chat at https://gitter.im/Positron-Contributors/community](https://badges.gitter.im/Positron-Contributors/community.svg)](https://gitter.im/Positron-Contributors/community?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge&utm_content=badge)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
![Github CI workflow badge](https://github.com/theRealProHacker/Positron/actions/workflows/run-test.yml/badge.svg)

# Positron

Positron is a python package that allows you to write simple and elegant HTML, CSS and Python code and have a desktop app running.

## Why you should use it

You are tired of the ugliness of tkinter, already know web technologies and don't want to learn new frameworks like QT or Kivy and Electron is too slow for you then this is the perfect place to start!


# How to get started

You need Python >= 3.10 and Git installed

```shell
git clone https://github.com/theRealProHacker/Positron.git
pip install Positron
```

There are some alternative installations for a live console, markdown support and to run the examples respectively

```shell
pip install Positron[console]
pip install Positron[markdown]
pip install Positron[examples]
```

Now you can create your project using Positron. For a good example with a step-by-step guide look [here](https://github.com/theRealProHacker/Positron/wiki/Example:-Calculator). 

If you have any questions, don't be shy to [ask a question](https://github.com/theRealProHacker/Positron/discussions/new?category=q-a)

Alternatively, you can also install Positron using a [virtual environment](https://docs.python.org/3/library/venv.html) if you prefer. 

# Contributing

All contributions are highly welcome and everyone is able to make a contribution. 
For more information on how to contribute and raise security issues look into [CONTRIBUTING.md](CONTRIBUTING.md)

# Visualization of the codebase
Uses [repo-visualization](https://githubnext.com/projects/repo-visualization/) by [Amelia Wattenberger](https://wattenberger.com/)

Check out the [live version](https://mango-dune-07a8b7110.1.azurestaticapps.net/?repo=theRealProHacker%2FPositron)

![Visualization of the codebase](./diagram.svg)


### The Name

[Electron](https://github.com/electron/electron) is a very popular framework that gives a very similar promise. 
The idea is that you can write a desktop app with just HTML/CSS/JS - all of which a typical web developer is already familiar with. 

Positron is a spin-off of on Electron and makes a pun off the fact that a positron is the physical anti-matter to an electron. 
Also, **E**lectron uses **E**CMAScript and **P**ositron uses **P**ython

> I initially thought the name was really brilliant and original until I randomly searched for Positron and found like 5 other projects with the same name. One of them an Electron clone by Mozilla 😂.

### Why Electron doesn't work

You can use Electron that calls python code. However, the problems of Electron are well known. 

Specifically, Electron creates a server and a Chromium client that communicate per IPC. This makes Electron both relatively slow and also it uses **huge** amounts of memory. Apps that use Electron like VSCode or Discord pretty quickly add up to GBs of RAM usage. 4GB vanish quickly when you for example have 2 Browsers and 2 Electron apps open. When the OS has little RAM left it will start swapping RAM in and out of disk and this will make your whole computer lag a lot.

Also, Electron has pretty slow load times. If you start any other regular app (a Flutter app for example), it seems like it opens almost instantly. However, Electron takes a few seconds to load and it really becomes obvious to the user. 

Apart from this little thing, Electron is really great, if you know how to use it.

# Sources

## MVPs
- [MDN](developer.mozilla.org)
- [The official HTML specifications](html.spec.whatwg.org)
- [How Browsers work](https://web.dev/howbrowserswork/)
- [Web Browser Engineering](https://browser.engineering/)
- Just to be honest [StackOverflow](https://stackoverflow.com)
