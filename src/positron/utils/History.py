from positron.types import V_T


class History(list[V_T]):
    """
    A generalized History of things. Subclasses list for maximum usability
    """

    cur = -1

    @property
    def current(self):
        """
        The current point in history
        """
        # TODO: What should we do when the history is empty?
        return self[self.cur]

    def peek_back(self) -> V_T:
        cur = max(0, self.cur - 1)
        return self[cur]

    def peek_for(self) -> V_T:
        cur = min(len(self) - 1, self.cur + 1)
        return self[cur]

    # Navigation

    def back(self):
        """
        Goes back in history
        """
        self.cur = max(0, self.cur - 1)
        return self.current

    def can_go_back(self) -> bool:
        """
        Whether there is history to go back to
        """
        return bool(self.cur)

    def forward(self):
        """
        Move forward in history
        """
        self.cur = min(len(self) - 1, self.cur + 1)
        return self.current

    def can_go_forward(self) -> bool:
        """
        Whether we can go back into the future
        """
        return bool(self.cur - len(self) + 1)

    def add_entry(self, entry: V_T):
        """
        Add an entry to the history
        """
        self.cur += 1
        self[:] = [*self[: self.cur], entry]

    def clear(self):
        """
        Clear history
        """
        super().clear()
        del self.cur
