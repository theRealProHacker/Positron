"""
The parsing that is mostly independent of Style.py
"""
from contextlib import contextmanager

import tinycss


class CustomCSSParser(tinycss.CSS21Parser):
    def parse_declaration(self, tokens: list[tinycss.token_data.Token]):
        # custom properties like
        # --my-custom-property: 10px
        first_token, second_token, *rest = tokens
        if first_token.value == "-" and second_token.type == "IDENT":
            value = first_token.value + second_token.value
            tokens = [
                tinycss.token_data.Token(
                    "IDENT", value, value, None, first_token.line, first_token.column
                ),
                *rest,
            ]
        return super().parse_declaration(tokens)

    def parse_media(self, tokens):
        # a bit hacky but we do the real parsing in MediaQuery.py anyway
        return tokens


Parser = CustomCSSParser()


current_file: str = ""


@contextmanager
def set_curr_file(file: str):
    global current_file
    current_file = file
    try:
        yield
    finally:
        current_file = ""


IMPORTANT = " !important"


def parse_important(s: str) -> tuple[str, bool]:
    return (s[: -len(IMPORTANT)], True) if s.endswith(IMPORTANT) else (s, False)
