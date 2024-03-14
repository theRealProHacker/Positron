# The Audio Element

The `<audio>` element is a very simple element in general. 
It has some audio source connected to it, that it should play.

Visually it resembles a common videoplayer with a play/pause button, 
a sound slider and a track slider as well as progress and length expressed as numbers.

These visual elements also need to be centered (and layouted in general) and receive mouse and keyboard inputs. 

## Layout

The size of the player can be adjusted with css. 
Depending on the size the inner controls need to be adjusted and at a certain small size even hidden:

The size of the player depends on the length of the longer side.
If the width is greater than the height, then the player is ltr.
If the height is greater than the width, then the player is ttb.

The controls should have some spacing on the main axis and be centered on the cross axis. 

At very large sizes, the player should mostly expand the track slider and leave the other controls as they are. 
At smaller sizes the track slider should shrink to some minimal size. As soon as all controls have reached their minimal sizes they should be removed in this order:
    1. Volume control
    2. Track slider
    3. Text
    4. The play/pause button is never removed but shrinks continuously with the smaller dimension.


## User Input

- Click on play/pause to play/pause. The action you will take is always displayed.
- The track slider shows the progress of the audio file and allows the user to scrub through the audio
- Click on sound icon to mute. The sound icon looks differently depending on the volume level.
- Hover on sound icon to display the volume slider. 
- All of the elements should also be focusable elements in their own regards

