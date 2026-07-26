from typing import Dict
from .. import validator
from .._http_client import HttpClient
from ..exceptions import CatalystConnectorError
from .._constants import (
    CLIENT_ID,
    CLIENT_SECRET,
    AUTH_URL,
    REFRESH_URL,
    CONNECTOR_NAME,
    REFRESH_TOKEN,
    EXPIRES_IN,
    REDIRECT_URL,
    GRANT_TYPE,
    CODE,
    RequestMethod,
    ACCESS_TOKEN
)


class Connector:
    def __init__(self, connection_instance, connector_details: Dict[str, str]) -> None:
        self._app = connection_instance._app
        self._requester: HttpClient = connection_instance._requester
        self.connector_name = connector_details.get(CONNECTOR_NAME)
        self.auth_url = connector_details.get(AUTH_URL)
        self.refresh_url = connector_details.get(REFRESH_URL)
        self.refresh_token = connector_details.get(REFRESH_TOKEN)
        self.client_id = connector_details.get(CLIENT_ID)
        self.client_secret = connector_details.get(CLIENT_SECRET)
        self.expires_in = (int(connector_details.get(EXPIRES_IN))
                           if connector_details.get(EXPIRES_IN)
                           else None)
        self.redirect_url = connector_details.get(REDIRECT_URL)
        self.access_token = None

    @property
    def _connector_name(self):
        return 'ZC_CONN_' + self.connector_name

    def generate_access_token(self, code: str) -> str:
        validator.is_non_empty_string(code, 'grant_token', CatalystConnectorError)
        # if not self.redirect_url or not isinstance(self.redirect_url, str):
        #     raise CatalystConnectorError(
        #         'Invalid Argument',
        #         'Value provided for redirect_url is expected to be a non empty string',
        #         code
        #     )
        resp = self._requester.request(
            method=RequestMethod().POST,
            url=self.auth_url,
            data={
                GRANT_TYPE: 'authorization_code',
                CODE: code,
                CLIENT_ID: self.client_id,
                CLIENT_SECRET: self.client_secret,
                # REDIRECT_URL: self.redirect_url
            }
        )
        token_obj = resp.response_json
        try:
            self.access_token = token_obj[ACCESS_TOKEN]
            self.refresh_token = token_obj[REFRESH_TOKEN]
            self.expires_in = token_obj[EXPIRES_IN]
        except KeyError as err:
            raise CatalystConnectorError(
                'Invalid Auth Response',
                f'{str(err)} is missing in the response json',
                token_obj
            ) from None
        self._persist_token_in_cache()
        return self.access_token

    def get_access_token(self):
        cached_token = self._app.cache().segment().get(self._connector_name)
        value = cached_token['cache_value']

        if value:
            time = 3600000 - int(cached_token['ttl_in_milliseconds'])
            if not self.expires_in:
                return value
            if self.expires_in and time <= (self.expires_in * 1000):
                return value

        validator.is_non_empty_string(self.refresh_token, 'refresh_token', CatalystConnectorError)

        resp = self._requester.request(
            method=RequestMethod.POST,
            url=self.refresh_url,
            data={
                GRANT_TYPE: 'refresh_token',
                CLIENT_ID: self.client_id,
                CLIENT_SECRET: self.client_secret,
                REFRESH_TOKEN: self.refresh_token
            }
        )
        token_obj = resp.response_json
        try:
            self.access_token = token_obj[ACCESS_TOKEN]
            self.expires_in = int(token_obj[EXPIRES_IN])
        except KeyError as err:
            raise CatalystConnectorError(
                'Invalid Auth Response',
                f'{str(err)} is missing in the response json',
                token_obj
            ) from None
        self._persist_token_in_cache()
        return self.access_token

    def _persist_token_in_cache(self):
        return self._app.cache().segment().put(self._connector_name, self.access_token, 1)
