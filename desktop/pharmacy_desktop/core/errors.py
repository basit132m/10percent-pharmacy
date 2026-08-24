"""Domain errors. The UI turns these into message boxes; anything else is a bug."""


class PharmacyError(Exception):
    """Base class for every expected, user-facing failure."""


class ValidationError(PharmacyError):
    """The data the user typed cannot be accepted."""


class NotFoundError(PharmacyError):
    """A record that was asked for does not exist."""


class AuthError(PharmacyError):
    """Login failed, or the signed-in user may not do this."""


class InsufficientStockError(PharmacyError):
    """A sale asked for more units than are on the shelf."""
