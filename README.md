# HuntAPI for Dify

[HuntAPI](https://www.huntapi.com) reads and downloads public videos. This plugin gives Dify agents, workflows and chatflows the metadata of a video (title, channel, duration, views, likes, upload date, thumbnail) and download links for the video or its audio, from YouTube, TikTok, Instagram, Facebook, Vimeo, X, Twitch, Reddit and many more sites.

**Author:** huntapi · **Source:** https://github.com/huntapi/dify-plugin-huntapi · **Contact:** contact@huntapi.com

## Tools

| Tool | What it does |
| --- | --- |
| **Media Metadata** | Title, description, channel, duration, views, likes, upload date, thumbnail and size, without downloading. 1 credit. |
| **Download Video** | Downloads the video and returns a link. **Quality** goes from 360p to the best available, **Format** is MP4, WebM or MKV. 1 credit. |
| **Download Audio** | Extracts the audio and returns a link, as MP3, M4A or WAV, from 128 kbps to the best available. 1 credit. |
| **Job Status** | Status, progress and download link of a download job that took longer than the wait. Free. |

Each tool returns a text message, which agents read, and a JSON message for workflow variables. The download tools also return the download link. Errors such as an invalid key, missing credits or a rate limit come back as a text message, and the API key never appears in it.

Downloads run as jobs on HuntAPI's servers. **Download Video** and **Download Audio** wait up to 140 seconds for the link; a longer job returns its job id, and **Job Status** gives the link once it is done. The file stays on HuntAPI's storage behind the link. Download only content you have the right to download.

## Setup

1. Create an account and copy your API key at [app.huntapi.com](https://app.huntapi.com).
2. In Dify, install the **HuntAPI** plugin from the Marketplace.
3. Open **Tools → HuntAPI → Authorize** and paste the API key. Dify checks it with a request that costs no credits.
4. Add the tools to an agent, a workflow or a chatflow.

## Requirements

- Dify 1.0.0 or later.
- Outbound HTTPS access to `api.huntapi.com`.
- A HuntAPI API key. Usage counts against your HuntAPI credits; see [www.huntapi.com/pricing](https://www.huntapi.com/pricing).

## Privacy

See [PRIVACY.md](PRIVACY.md).

## Development

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt pytest pyyaml
.venv/bin/pytest
```

The `Package` workflow builds the `.difypkg` with Dify's plugin CLI and attaches it to a GitHub release when the version in `manifest.yaml` changes.
