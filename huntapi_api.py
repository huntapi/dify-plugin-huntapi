"""Calls to the HuntAPI API and conversion of its responses to tool output.

The provider and the tools share this module. A tool file must hold only one
Tool subclass, so the shared code is here and not in tools/.
"""

import json
from collections.abc import Generator
from typing import Any
from urllib.parse import quote

import requests

API_BASE = "https://api.huntapi.com"
USER_AGENT = "huntapi-dify-plugin/0.0.1"
CREDENTIALS_PATH = "/v1/usage"
CREDENTIALS_TIMEOUT = 30
DEFAULT_TIMEOUT = 60
MAX_TEXT = 20000


class ApiError(Exception):
    """An error message that is safe to show to the user and to the model. It never contains the key."""


def api_key(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ApiError("A HuntAPI API key is required.")
    return value.strip()


def _headers(secret: str) -> dict:
    headers = {"Accept": "application/json", "User-Agent": USER_AGENT}
    headers["x-api-key"] = secret
    return headers


def _error_message(response: requests.Response) -> str:
    detail = ""
    try:
        body = response.json()
    except ValueError:
        body = None
    if isinstance(body, dict):
        error = body.get("error") or body.get("message") or ""
        if isinstance(error, dict):
            error = error.get("message") or ""
        detail = str(error)
    status = response.status_code
    if status == 401 and "rate limit" in detail.lower():
        label = "Rate limit exceeded. Try again soon."
    elif status == 401:
        label = "The API key is not valid."
    elif status == 402:
        label = "Not enough credits."
    elif status == 429:
        label = "Rate limit exceeded. Try again soon."
    else:
        label = "The request failed."
    return f"HuntAPI error {status}: {label}" + (f" ({detail[:300]})" if detail and detail not in label else "")


def request(
    method: str,
    path: str,
    key: Any,
    params: dict | None = None,
    body: dict | None = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> requests.Response:
    """Call API_BASE + path with the key, and return the successful response."""
    secret = api_key(key)
    try:
        response = requests.request(
            method, API_BASE + path, params=params, json=body, headers=_headers(secret), timeout=timeout
        )
    except requests.Timeout:
        raise ApiError("HuntAPI did not answer in time. Try again.") from None
    except requests.RequestException:
        raise ApiError("Could not connect to api.huntapi.com. Check the network.") from None
    if response.status_code >= 400:
        raise ApiError(_error_message(response).replace(secret, "***"))
    return response


def check_credentials(key: Any) -> None:
    """The credentials endpoint costs no credits and fails when the key is not valid."""
    request("GET", CREDENTIALS_PATH, key, timeout=CREDENTIALS_TIMEOUT)


def body_json(response: requests.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        raise ApiError("HuntAPI sent a response that is not JSON.") from None


def _value(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def collect(params: dict, fields: dict[str, str], required: tuple = ()) -> dict:
    """Map tool parameters to API parameters, skipping empty values and checking the required ones."""
    out = {}
    for name, api_name in fields.items():
        value = _value(params.get(name))
        if value is None or value == "":
            if name in required:
                raise ApiError(f"{name} is required.")
            continue
        out[api_name] = value
    return out


def fill_path(path: str, values: dict) -> str:
    """Move values named in the path ("/jobs/{id}") into it, escaped."""
    for name in list(values):
        if "{" + name + "}" in path:
            path = path.replace("{" + name + "}", quote(str(values.pop(name)), safe=""))
    return path


def query_values(values: dict) -> dict:
    """Booleans as true/false, as the API expects them in a query string."""
    return {k: ("true" if v else "false") if isinstance(v, bool) else v for k, v in values.items()}


def as_text(data: Any) -> str:
    text = json.dumps(data, ensure_ascii=False, indent=2)
    return text if len(text) <= MAX_TEXT else text[:MAX_TEXT] + "\n… (cut)"


def call(
    tool,
    params: dict,
    method: str,
    path: str,
    fields: dict[str, str],
    required: tuple = (),
    fixed: dict | None = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> Generator:
    """Run one API call for a tool: a text message for agents, then a JSON message for workflows."""
    try:
        values = {**(fixed or {}), **collect(params, fields, required)}
        path = fill_path(path, values)
        in_query = method in ("GET", "DELETE")
        if in_query:
            values = query_values(values)
        response = request(
            method,
            path,
            tool.runtime.credentials.get("api_key"),
            params=values if in_query else None,
            body=None if in_query else values,
            timeout=timeout,
        )
        data = body_json(response)
    except ApiError as error:
        yield tool.create_text_message(str(error))
        return
    yield tool.create_text_message(as_text(data))
    yield tool.create_json_message(data if isinstance(data, dict) else {"results": data})


# Download jobs

import time  # noqa: E402

JOB_WAIT = 140
POLL_EVERY = 3
FAILED = ("Error", "NotFound", "BadRequest")


def download(tool, params: dict, path: str, fields: dict):
    """Start a download job and wait for its link, up to JOB_WAIT seconds."""
    key = tool.runtime.credentials.get("api_key")
    try:
        values = collect(params, fields, ("url",))
        job_id = body_json(request("GET", path, key, params=values)).get("job_id")
        if not isinstance(job_id, str) or not job_id:
            raise ApiError("HuntAPI did not return a job id.")
        deadline = time.monotonic() + JOB_WAIT
        while True:
            job = body_json(request("GET", fill_path("/v1/jobs/{id}", {"id": job_id}), key))
            status = job.get("status") if isinstance(job, dict) else None
            if status == "CompletedJob" or status in FAILED or time.monotonic() >= deadline:
                break
            time.sleep(POLL_EVERY)
    except ApiError as error:
        yield tool.create_text_message(str(error))
        return
    result = job.get("result") if isinstance(job.get("result"), dict) else {}
    link = result.get("response")
    if status == "CompletedJob" and isinstance(link, str) and link:
        title = (result.get("metadata") or {}).get("title") if isinstance(result.get("metadata"), dict) else None
        yield tool.create_text_message(f"Download link{f' for {title}' if title else ''}: {link}")
        yield tool.create_link_message(link)
    elif status in FAILED:
        yield tool.create_text_message(
            f"The download failed ({status}): {job.get('error') or 'private, deleted, age-restricted or unsupported content'}."
        )
    else:
        yield tool.create_text_message(
            f"The download is still running ({job.get('progress') or 0}%). Check it later with Job Status and job id {job_id}."
        )
    yield tool.create_json_message({"job_id": job_id, **job})
