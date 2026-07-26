
class CatalystError(Exception):
    def __init__(self, code, message, value=None):
        self._code = code
        self._message = message
        self._value = value
        Exception.__init__(self, self.to_string())

    @property
    def code(self):
        return self._code

    @property
    def message(self):
        return self._message

    @property
    def value(self):
        return self._value

    @property
    def status_code(self):
        return None

    def to_json(self):
        json_dict = {
            'code': self._code,
            'message': self._message
        }
        if self._value:
            json_dict['value'] = self._value
        return json_dict

    def to_string(self):
        return str(self.to_json())


class CatalystCredentialError(CatalystError):
    def __init__(self, code, message, value=None):
        CatalystError.__init__(self, code, message, value)


class CatalystAppError(CatalystError):
    def __init__(self, code, message, value=None):
        CatalystError.__init__(self, code, message, value)


class CatalystAPIError(CatalystError):
    def __init__(self, code, message, value=None, http_status_code=None):
        self.http_status_code = http_status_code
        CatalystError.__init__(self, code, message, value)

    @property
    def status_code(self):
        return self.http_status_code


class CatalystCacheError(CatalystError):
    def __init__(self, code, message, value=None):
        CatalystError.__init__(self, code, message, value)


class CatalystDatastoreError(CatalystError):
    def __init__(self, code, message, value=None):
        CatalystError.__init__(self, code, message, value)


class CatalystFunctionError(CatalystError):
    def __init__(self, code, message, value=None):
        CatalystError.__init__(self, code, message, value)


class CatalystMailError(CatalystError):
    def __init__(self, code, message, value=None):
        CatalystError.__init__(self, code, message, value)


class CatalystFilestoreError(CatalystError):
    def __init__(self, code, message, value=None):
        CatalystError.__init__(self, code, message, value)


class CatalystAuthenticationError(CatalystError):
    def __init__(self, code, message, value=None):
        CatalystError.__init__(self, code, message, value)


class CatalystZCQLError(CatalystError):
    def __init__(self, code, message, value=None):
        CatalystError.__init__(self, code, message, value)


class CatalystCronError(CatalystError):
    def __init__(self, code, message, value=None):
        CatalystError.__init__(self, code, message, value)


class CatalystCircuitError(CatalystError):
    def __init__(self, code, message, value=None):
        CatalystError.__init__(self, code, message, value)


class CatalystConnectorError(CatalystError):
    def __init__(self, code, message, value=None):
        CatalystError.__init__(self, code, message, value)


class CatalystPushNotificationError(CatalystError):
    def __init__(self, code, message, value=None):
        CatalystError.__init__(self, code, message, value)


class CatalystSearchError(CatalystError):
    def __init__(self, code, message, value=None):
        CatalystError.__init__(self, code, message, value)


class CatalystZiaError(CatalystError):
    def __init__(self, code, message, value=None):
        CatalystError.__init__(self, code, message, value)


class BrowserLogicError(CatalystError):
    def __init__(self, code, message, value=None):
        CatalystError.__init__(self, code, message, value)


class QuickMLError(CatalystError):
    def __init__(self, code, message, value=None):
        CatalystError.__init__(self, code, message, value)
