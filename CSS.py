"""
A list of stylesheets that applies styles to elements automatically
"""
from own_types import style_input

at_rule = tuple[str, dict] # eg mediarule
value = tuple[str,bool] # actual value + important
style = dict[str,tuple[str, bool]]
style_rule = tuple[str, style]
"""
A style with a selector
Example:
p {
    color: red !important;
} -> (p, {color: (red, True)})
"""
def join_styles(style1: style, style2: style):
    """
    Join two styles. Prefers the first
    """
    chain = style1|style2
    return {
        **{k:chain[k] for k in style1 ^ style2.keys()}, # all keys that are in one but not both # type: ignore[list-item]
        **{k:style2[k] if style2[k][1] and not style1[k][1] else style1[k] 
        for k in style1 & style2.keys()} # all keys that are in both
    }

# def combine_styles(*styles: style):
#     from functools import reduce
#     """
#     Join multiple styles
#     """
#     return reduce(join_styles, styles)

def remove_important(style: style)->style_input:
    """
    Remove the information whether a value in the style is important
    """
    return {
        k: v[0] for k, v in style.items()
    }

media = tuple[int,int] # just the window size right now

class StyleSheet(list[at_rule|style_rule]):
    last_media = None
    @property
    def all_rules(self)->list[style_rule]:
        return (
            [rule for rule in self if isinstance(rule, dict)]
            + [reduced for rule in self if isinstance(rule, tuple) 
                and (reduced:=self.reduce(rule)) is not None]
        )
    def reduce(self, rule: at_rule)->style_rule:
        """
        Reduce a rule to a style_rule
        """
        if isinstance(rule, at_rule):
            return None
        else:
            return rule



def parse_style(s: str)->StyleSheet:
    """
    Parse into a StyleSheet
    """
    pass

def parse_important(s: str)->value:
    x = s.split()
    return (' '.join(x[:-1]),True) if x[-1] == "!important" else (' '.join(x),False)

def pre_parse_style(s: str)->dict[str,str]:
    data = s.removeprefix("{").removesuffix("}").strip(
        ).split(";")
    return {
        k:(v,False) for k,v in [
            x.split(":") for x in data
        ]
    }
