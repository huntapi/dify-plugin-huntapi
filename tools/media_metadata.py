from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from huntapi_api import call


class HuntAPIMediaMetadataTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        yield from call(self, tool_parameters, "GET", "/v1/media/metadata", {"url": "query"}, required=("url",))
