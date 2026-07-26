import os
from typing import Dict
import requests
from requests import Response
from urllib3.util import retry
from .exceptions import CatalystAPIError
from .credentials import (
    AccessTokenCredential,
    RefreshTokenCredential,
    TicketCredential,
    CatalystCredential
)
from ._constants import (
    APP_DOMAIN,
    APP_VERSION_V1,
    USER_AGENT,
    SDK_VERSION,
    AUTHORIZATION,
    TICKET_PREFIX,
    OAUTH_PREFIX,
    COOKIE_HEADER,
    CSRF_HEADER,
    IS_LOCAL,
    PROJECT_KEY,
    PROJECT_KEY_NAME,
    ENVIRONMENT_KEY_NAME,
    ENVIRONMENT,
    PROJECT_SECRET_KEY,
    USER_KEY_NAME,
    PROJECT_DOMAIN,
    CATALYST_ORG_ID_KEY,
    X_CATALYST_ORG_ENV_KEY,
    AcceptHeader,
    CredentialUser,
    ProjectHeader,
    CatalystService
)

USERAGENT_HEADER = {USER_AGENT: "zc-python-sdk/" + SDK_VERSION}

# Default timeout for connect and read operation in seconds
DEFAULT_TIMEOUT = (60, 30)

DEFAULT_RETRY_CONFIG = retry.Retry(
    connect=2,
    read=1,
    status=4,
    status_forcelist=[500, 502, 503, 504],
    raise_on_status=False,
    backoff_factor=0.5
)


class DefaultHttpResponse:
    def __init__(self, resp: Response):
        self._response = resp
        self._status_code = resp.status_code
        self._headers = resp.headers
        self.check_status()

    @property
    def response(self):
        return self._response

    @property
    def status_code(self):
        return self._status_code

    @property
    def headers(self):
        return self._headers

    @property
    def response_json(self):
        try:
            return self._response.json()
        except:
            raise CatalystAPIError(
                'UNPARSABLE_RESPONSE',
                'unable to parse the response json'
            ) from None

    def check_status(self):
        if self._status_code is None:
            raise CatalystAPIError(
                'UNKNOWN_STATUSCODE',
                'unable to obtain status code from response', self.response_json
            )

        if self._status_code not in range(200, 300):
            data = self.response_json.get('data')
            if data:
                error_code = data.get('error_code')
                message = data.get('message')
                if error_code and message:
                    raise CatalystAPIError(
                        error_code,
                        message,
                        http_status_code=self._status_code
                    )
            raise CatalystAPIError(
                'API_ERROR',
                (f'Request failed with status {self._status_code} and '
                 f'response data : {self.response_json}')
            )


class HttpClient:
    def __init__(
        self,
        app=None,
        base_url=None,
        retries=DEFAULT_RETRY_CONFIG,
        timeout=DEFAULT_TIMEOUT
    ):
        self._session = requests.session()
        self._timeout = timeout
        self._base_url = base_url
        if retries:
            self._session.mount('http://', requests.adapters.HTTPAdapter(max_retries=retries))
            self._session.mount('https://', requests.adapters.HTTPAdapter(max_retries=retries))
        self._app = app

    @property
    def session(self):
        return self._session

    @property
    def base_url(self):
        return self._base_url

    @property
    def timeout(self):
        return self._timeout

    def request(
        self,
        method: str,
        url: str = None,
        path: str = None,
        user=CredentialUser.ADMIN,
        catalyst_service=None,
        **kwargs
    ):
        if 'timeout' not in kwargs:
            kwargs['timeout'] = self._timeout

        if 'headers' not in kwargs:
            kwargs['headers'] = {}
        headers = kwargs['headers']
        headers.update(USERAGENT_HEADER)

        if self._app is not None:
            from .catalyst_app import CatalystApp  # pylint: disable=import-outside-toplevel
            if not isinstance(self._app, CatalystApp):
                raise ValueError(
                    'Invalid app provided to make requests. App must be an instance of CatalystApp'
                )

            headers[PROJECT_KEY_NAME] = str(self._app.config.get(PROJECT_KEY))
            headers[ENVIRONMENT_KEY_NAME] = self._app.config.get(ENVIRONMENT)
            headers[ENVIRONMENT] = self._app.config.get(ENVIRONMENT)
            headers[USER_KEY_NAME] = self._app.credential.current_user_type()
            if os.getenv(X_CATALYST_ORG_ENV_KEY) is not None:
                headers[CATALYST_ORG_ID_KEY] = os.getenv(X_CATALYST_ORG_ENV_KEY)

            # setting project key in headers if it's present
            if self._app.config.get(PROJECT_SECRET_KEY):
                headers[ProjectHeader.project_secret_key] = self._app.config['project_secret_key']

            user = self._app.credential.current_user()

            #special handling for CLI
            if IS_LOCAL == 'true':
                if user == CredentialUser.ADMIN:
                    self._base_url = \
                        'https://' + APP_DOMAIN.replace('https://', '').replace('http://', '')
                elif user == CredentialUser.USER:
                    self._base_url = 'https://' + self._app.config.get(PROJECT_DOMAIN)

            if catalyst_service:
                project_id = self._app.config.get('project_id')
                path = catalyst_service + APP_VERSION_V1 + f'/project/{project_id}' + (path or '')
                accept_header = [AcceptHeader.VALUE, headers.get(AcceptHeader.KEY)]
            if catalyst_service == CatalystService.SERVERLESS:
                headers[AcceptHeader.KEY] = ','.join(filter(lambda x: x is not None, accept_header))

        self._base_url = self._base_url or APP_DOMAIN

        url = url or (os.path.join(self._base_url, path))
        resp = self._session.request(method, url, **kwargs)

        return DefaultHttpResponse(resp)

    def close(self):
        self._session.close()
        self._session = None


class AuthorizedHttpClient(HttpClient):
    def __init__(
        self,
        app
    ):
        super().__init__(app)

    def request(
        self,
        method: str,
        url: str = None,
        path: str = None,
        user=CredentialUser.USER,
        catalyst_service=CatalystService.SERVERLESS,
        **kwargs
    ):
        self._app.credential._switch_user(user)  # pylint: disable=protected-access
        self._authenticate_request(kwargs)
        return super().request(method, url, path, user, catalyst_service, **kwargs)

    def _authenticate_request(self, kwargs):

        # if 'headers' not in kwargs:
        #     kwargs['headers'] = {}
        # headers = kwargs['headers']

        headers = kwargs['headers'] = {} if 'headers' not in kwargs else kwargs['headers']

        credential = self._app.credential
        if isinstance(credential, (AccessTokenCredential, RefreshTokenCredential)):
            AuthorizedHttpClient.set_oauth_header(headers, credential.token())
        if isinstance(credential, TicketCredential):
            AuthorizedHttpClient.set_ticket_header(headers, credential.token())
        if isinstance(credential, CatalystCredential):
            cred_type, token = credential.token()
            if cred_type == 'AccessTokenCredential':
                AuthorizedHttpClient.set_oauth_header(headers, token)
            elif cred_type == 'TicketCredential':
                AuthorizedHttpClient.set_ticket_header(headers, token)
            elif cred_type == 'CookieCredential':
                headers.update({COOKIE_HEADER: token[0]})
                headers.update({CSRF_HEADER: token[1]})

    @staticmethod
    def set_oauth_header(headers: Dict, token: str):
        headers.update({AUTHORIZATION: OAUTH_PREFIX + token})

    @staticmethod
    def set_ticket_header(headers: Dict, ticket: str):
        headers.update({AUTHORIZATION: TICKET_PREFIX + ticket})
