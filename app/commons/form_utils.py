from enum import Enum
from flask_babel import lazy_gettext


class FormEnum(Enum):
    @classmethod
    def choices(cls):
        return [(choice, choice.loc_text()) for choice in cls]

    @classmethod
    def coerce(cls, item):
        return cls(str(item)) if not isinstance(item, cls) else item

    def loc_text(self):
        return ''

    def __str__(self):
        return str(self.value)