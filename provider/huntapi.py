from typing import Any

from dify_plugin import ToolProvider
from dify_plugin.errors.tool import ToolProviderCredentialValidationError

from huntapi_api import ApiError, check_credentials


class HuntAPIProvider(ToolProvider):
    def _validate_credentials(self, credentials: dict[str, Any]) -> None:
        # /v1/usage costs no credits. It fails when the key is not valid.
        try:
            check_credentials(credentials.get("api_key"))
        except ApiError as error:
            raise ToolProviderCredentialValidationError(str(error)) from None
