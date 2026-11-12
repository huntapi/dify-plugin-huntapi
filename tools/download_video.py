from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from huntapi_api import download


class HuntAPIDownloadVideoTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        yield from download(
            self,
            tool_parameters,
            "/v1/video/download",
            {"url": "query", "video_quality": "video_quality", "video_format": "video_format"},
        )
