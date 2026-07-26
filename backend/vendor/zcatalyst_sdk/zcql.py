import os
from typing import Dict, List, TypedDict
from .types import Component
from .exceptions import CatalystZCQLError
from ._http_client import AuthorizedHttpClient
from ._constants import (
    RequestMethod,
    CredentialUser,
    Components,
    AcceptHeader,
    ZCQL_PARSER
)

ZcqlQueryOutput = TypedDict('ZcqlQueryOutput', {'table_name': Dict})


class Zcql(Component):
    def __init__(self, app) -> None:
        self._app = app
        self._requester = AuthorizedHttpClient(self._app)

    def get_component_name(self):
        return Components.ZCQL

    def execute_query(self, query: str) -> List[ZcqlQueryOutput]:
        if not query or not isinstance(query, str):
            raise CatalystZCQLError(
                'INVALID_QUERY',
                'Query must be a non empty string'
            )
        req_json = {
            'query': query
        }
        resp = self._requester.request(
            method=RequestMethod.POST,
            path='/query',
            json=req_json,
            user=CredentialUser.USER,
            headers={AcceptHeader.KEY: AcceptHeader.ZCQL} if os.getenv(ZCQL_PARSER) == 'V2' else {}
        )
        resp_json = resp.response_json
        return resp_json.get('data')
