class XIBError(Exception):
    pass


class BadXibFormat(XIBError):
    pass


class UnknownAttribute(XIBError):
    pass


class UnknownAttributeValue(XIBError):
    pass


class UnknownTag(XIBError):
    pass


class MultipleRootObjects(XIBError):
    pass
