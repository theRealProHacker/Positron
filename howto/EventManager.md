# The EventManager

An EventManager is responsible for taking hardware events and emitting events depending on the applications state.
Additionally, the EventManager accepts callbacks to be called when a certain event happens.

Probably the most important events are mouse (often called `pointing device`) events. The EventManager should not just emit events but also tell the DOM things like hover, active, focus, etc. 

If I understood the specs correctly, there is always just a single Element that is `:hover`ed over (`designated`), `:active` (`being activated`) or clicked (`activated`). But that always also effects the surrounding elements either through bubbling or through selector matching.

For example a label also matches `:active` when the labeled element (likely an input element) is the active element. 