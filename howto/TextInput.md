# Text & Input
This is related to the InputElement.

# The Text Cursor

The text cursor is the thing that blinks when you edit text. It must be distinguished from the mouse cursor, which is the thing that moves when you move your mouse. The text cursor controls what a keyboard input will do.

## How can a user interact with the cursor (Requirements)

1. Backspace will delete the character before the cursor
2. Delete will delete the character after the cursor
3. Arrow keys will move the cursor.
4. Pos1/Home and End will also move the cursor but more drastically. 
5. Ctrl or Shift can change the meaning of keyboard input.
6. Most keys will just insert a character at the cursor position and set the cursor after the input. 

Also, there could be many cursors on a single page that all react equally to all keyboard events. If two cursors overlap, they should be merged (could use a set). 

## Implementation

First, we need to put cursors somewhere. A global list of cursors that reference a TextElement and the position in the text might work.

```python
TextCursor = tuple[TextElement, int]
```

Now, all the cursors can be drawn inbetween the characters, when the text is drawn. The TextElements themselves also hold references to their global cursors. 

