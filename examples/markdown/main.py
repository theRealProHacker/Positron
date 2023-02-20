"""
An example on how to use the <md> element also using jinja
"""

from positron import *

set_cwd(__file__)

"""
with open("markdown.md") as f:
    markdown = f.read()

runSync("markdown.html?markdown=" + markdown)

# this might be easier to read:
runSync(URL("markdown.html", kwargs={"markdown": markdown}))
"""

# this makes the app hot reload when the markdown file is changed
from positron import watch_file

watch_file("markdown.md", Navigator.reload)

@route("/")
def index():
    with open("markdown.md") as f:
        markdown = f.read()
    
    load_dom("markdown.html", markdown = markdown)


runSync()
