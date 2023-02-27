def Opposite(attr: str) -> bool: ...
def SameAs(attr: str): ...
def GeneralAttribute(attr: str, default: str = "") -> str: ...
def EnumeratedAttribute(attr: str, range: set[str], default: str = "") -> str: ...
def NumberAttribute(attr: str, default: float = 0) -> float: ...
def BooleanAttribute(attr: str, default: bool = False) -> bool: ...
def ClassListAttribute(attr: str = "class", default: set[str] = set()) -> set[str]: ...
def DataAttribute(
    attr: str = "data", default: dict[str, str] = dict()
) -> dict[str, str]: ...
def InputValueAttribute(attr: str = "value", default: str = "") -> str: ...
