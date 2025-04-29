from openfreebuds.exceptions import OfbError


class OfbBackendDependencyMissingError(OfbError):
    pass

class BackendException(OfbError):
    """
    Exception raised for errors in the backend operations.
    This can include connection issues, device communication problems,
    or platform-specific errors.
    """
    pass
