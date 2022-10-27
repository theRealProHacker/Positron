# The InputElement

>  The <input> element is one of the most powerful and complex in all of HTML due to the sheer number of combinations of input types and attributes.

[MDN](https://developer.mozilla.org/en-US/docs/Web/HTML/Element/Input)

In other words, every input type is almost like its own element but all inputs share some similarities. 

I personally would split the input types into the following groups

# Text Inputs
text, tel, password, number, email, url and search
> Note: A big TODO is replacing any hard-coded data with config variables. This could also make the app more costumizable. For example you could set the passwords replace character with "😎" or you could set the default regex pattern for the telephone input. 
> Another Note: In real browsers the input types also have additional semantic meaning by providing the browser with information on what to autofill. 

## text
<input>  

This is the most general text type and also the default. The user can focus it and edit the input field freely. The field always has 1 line and slides with the cursor. When the user presses enter, the input looses focus and per default the associated form is submitted. The author can also set costraints on the input value. A form will only be submitted if all contained inputs are valid. Also, the input field will show a dialog describing the problem with the current value ("At least 3 characters are required"). 

## general text attributes
- `placeholder`: The placeholder is shown in an empty text field to guide the user what form of input to enter. I personally really love placeholders and prefer them over labels, even though they are condemned by spec writers because of their accessibility issues. To implement placeholder we just check if the value is empty and if so, we show the placeholder and set the texts opacity to some value`<`1.
```python
value: str = self.attrs["value"] or self.attrs.get("placeholder", "")
# we must not mutate the original color or self.cstyle due to style sharing. 
color = Color(self.cstyle["color"])
color.a = int(0.4 * color.a)
extra_style = {"color": color} if self.placeholder_shown else {}
```
- `size`: The size attribute sets how wide the input element should be in characters. So if the size is `20` then the input should be so wide that 20 average characters fit in. We define the average character's width to be the width of "M" for normal text. 
```python
if (_size := self.attrs.get("size")) is not None and _size.isnumeric():
    avrg_letter_width = self.font.metrics("M")[0][4] # index 4 is the advance
    width = int(_size) * avrg_letter_width
```
- `maxlength` and `minlength`: These are constraints on the length of an input. For example you might want a username to be at lest four characters long and not more than 20. This is pretty straightforward. 
```python
# in the validity check
if (max_length := self.attrs.get("maxlength")) is not None and len(
    value
) > max_length:
    return False
elif (min_length := self.attrs.get("minlength")) is not None and len(
    value
) < min_length:
    return False
```
- `pattern`: This is the most powerful validity check attribute; a regular expression that the input must match. 
```python
if (pattern := self.attrs.get("pattern")) is not None and not re.fullmatch(pattern, value):
    return False
```
- `required`: The input most not be empty on submission

## tel
<input type="tel">

This is the same as "text", except that if we have a virtual keyboard it should show a number pad. 
In the current implementation we have no control about the keyboard whatsoever.

## password
<input type="password">

So with the password input their is one big difference. The password that is being typed should be hidden. This is done by replacing the passwords characters with "*" or "•". 
```python
if not self.placeholder_shown and type_ == "password":
    value = "•" * len(value)
# because we know the exact characters widths:
avrg_letter_width = self.font.metrics("•" if type_ == "password" else "M")[0][4]
```
Additionally, I want to add a password visibility button to the end of the input. But that is something for later maybe. 

## number
<input type="number">
Here, the biggest difference is that the input should be a valid number. This is checked by the regex  
`[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?` (any valid python float).
Another difference are the input methods. The user can not just type but often also wheel or click provided up and down buttons.  
These buttons are not implemented yet. But the wheel was just implemented (and also reinvented) while writing this text (so there might still be bugs)
```python
# in on_wheel
if type_ == "number":
    with suppress(ValueError):
        self.attrs["value"] = nice_number(float(value or "0")+event.delta[0])
```
Also, the number input introduces two new attributes `max` and `min` which, unlike `maxlength` and `minlength`, actually look at the value to determine whether they hold valid. For number this is simple. 
> Note: In efficient languages this for-loop is unfold in compile time, because the iterated list is constant. Whether python does this, is left as a research exercise for the reader (I always wanted to say this some time 😂). 
```python
for constraint, operator in [
    ("max", operator.gt),
    ("min", operator.lt),
]:
    if constr := self.attrs.get(constraint):
        if type_ == "number":
            with suppress(ValueError):
                if operator(float(value), float(constr)):
                    return False
```

## email
<!-- <input type="email" multiple value="e1@example.com, e2@example.com"> -->
The email input has two key differences to the regular text input. Firstly, it is checked automatically against this regex 

    [\w\d.!#$%&'*+/=?^_\`{|}~-]+@[\w\d](?:[\w\d-]{0,61}[\w\d])?(?:\.[\w\d](?:[-\w\d]{0,61}[\w\d])?)*  
From [MDN](https://developer.mozilla.org/en-US/docs/Web/HTML/Element/input/email#basic_validation) (as always).  

Secondly, the email introduces the `multiple` attribute. That just means that a user can enter multiple emails seperated by commas. For some stupid reason this is allowed exactly for the file and email inputs. I don't understand why a user shouldn't also be able to input multiple urls or colors, but whatever. The emails should be checked individually. We do this by splitting on `\s*,\s*`
```python
values = (
    [value]
    if not type_ in ("email", "file")
    or self.attrs.get("multiple", "false") == "false"
    else re.split(r"\s*,\s*", value)
)
if (pattern := self.attrs.get("pattern")) is not None and any(
    not re.fullmatch(pattern, value) for value in values
):
    return False
return all(default_pattern.fullmatch(value) for value in values)
```

## url
<input type="url">  

Just like email but with a different regex, that I have not yet definitely decided on, because really almost anything could be an URL.

## search
<input type="search">  

The search input is a very recent addition and again has two main differences.  
Most importantly, it emits the search event either on every keystrike or when entered, depending on the `incremental` attribute. 
Also, search should be clearable with `ESC` and show a visible cross to clear the current query as well. Other visual changes like a search icon in the virtual keyboard are also common, but not required. 

# Physical Inputs
checkbox, radio, submit/button and range  
Physical inputs are inputs that look and feel a lot like physical objects.

## checkbox
<input type="checkbox">  

Default value is "on"  
The checkbox is very simple. It can be checked, indeterminate or unchecked. If it is not checked, it's value will not be represented in the form data. 
The checkbox adds another boolean attribute `checked` which determines the default checkboxes checked state.
If a checkbox is `required` the form cannot be submitted if the checkbox is not checked.

### Drawing the checkbox
A checkbox should be a slightly rounded box that is either unfilled (not checked) or filled with a check (checked) or filled with a crossed line (indeterminate).

## radio
<input type="radio">  

Radio buttons are just like checkboxes but are circular in shape. Most importantly, only one radio button of a radio button group can be checked. A radio group is defined by the `name` attribute.  
If any input in the group is `required`, at least one of the radio buttons has to be checked for any of them to be valid. 

## submit
<input type="submit">  

The submit is a button that if clicked submits the form. The process of submitting a form is not yet defined as we don't really have forms yet anyways. 

## button
<input type="button" disabled>  

Will not be implemented and should instead be replaced with the general button element!

## range
<input type="range">  

Default value is the average of `max` and `min`.  
This input type is also commonly referred to as a slider. There is a knob that can be moved on a line either horizontally or vertically depending on the `orient` attribute. `max`=`100`, `min`=`0` and `step`=`any` have a special meaning here, as they are enforced by the input.  
But apart from that this input works just like a number input.  
This input cannot be made invalid by a normal user but only progamatically by setting the value to a non-number. 

# Special Inputs
color and file  
Special inputs are inputs that are not inherently text inputs but instead show a pop-up when clicked on. In this pop-up you can then pick your value (or values). 

## color
<input type="color">  

What I have in mind is a really cool color picker that comes up on click.  
Colors are stored in the lowercased hexadecimal rgb notation, `#ffffff` for example.

## file
<input type="file">  

This input is one of the ugliest that I have seen in most browsers. We should do a better job. Important features are a system dialog on click that allows the user to natively choose files depending on the given `accept` attribute. For example `image/*` or `.docx`. The dialog should be non-blocking and asynchronously write back into the value of the file on completion. If the input is removed, so should the dialog. If the input is reactivated, the same system dialog should pop up again.

# Special Text Inputs
date, datetime-local, time, month and week
## date
TODO
## datetime-local
TODO
## time
TODO
## month
TODO
## week
TODO

# The Hidden Input
A hidden input is just not displayed. 
```python
# in compute
if self.type == "hidden":
    self.display = "none"
```

# Other general input properties
disabled, form, list, readonly, autofocus?

## disabled
If an InputElement is disabled, it is:

1. muted (higher opacity and more greys instead of black)
    This could be done by using the `input:disabled` selector.
2. Non-reactive:
    - No hover
    - No active
    - No focus
    - Not editable

## form
A "link" to a form by id.
An input automatically belongs to a form if it is a descendant of it. 
Through the form element any input can be linked to any form.
This linkage should be done bi-directional. 
The form knows all its inputs and the inputs know the form they belong to (1 to many relationship)

## list
A linked list (not that kind of linked list). 
The linked `<datalist>` gives a list of options the browser could display. 
> related: https://developer.mozilla.org/en-US/docs/Web/HTML/Element/datalist

## readonly
The content is not editable by the user. 

## autofocus
The element will be set to the focused element, when initialized.