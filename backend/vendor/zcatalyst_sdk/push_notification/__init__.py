from typing import Union
from ..types import Component
from ..exceptions import CatalystPushNotificationError
from .._http_client import AuthorizedHttpClient
from .. import validator
from .._constants import Components
from ._web_notificaton import WebNotification
from ._mobile_notification import MobileNotification


class PushNotification(Component):
    def __init__(self, app):
        self._app = app
        self._requester = AuthorizedHttpClient(app)

    def get_component_name(self):
        return Components.PUSH_NOTIFICATION

    def mobile(self, app_id: Union[int, str]):
        validator.is_non_empty_string_or_number(app_id, 'app_id', CatalystPushNotificationError)
        return MobileNotification(self, str(app_id))

    def web(self):
        return WebNotification(self)
