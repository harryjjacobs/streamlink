import logging

import requests
import streamlink
from streamlink.exceptions import NoPluginError, PluginError
from streamlink_cli.main import (
    setup_plugin_options,
    fetch_streams_with_retry,
    fetch_streams,
    format_valid_streams,
    handle_stream,
    StreamlinkCLIError,
    console,
    setup_streamlink,
    setup_plugins,
)

log = logging.getLogger("football_streams.cli")


def handle_url(
    url,
    retry_max=None,
    retry_streams=None,
    stream=None,
    default_stream=None,
    json=False,
    stream_url=False,
):
    """The URL handler.

    Attempts to resolve the URL to a plugin and then attempts
    to fetch a list of available streams.

    Proceeds to handle stream if user specified a valid one,
    otherwise output list of valid streams.

    """

    pluginname, pluginclass, resolved_url = streamlink.resolve_url(url)
    options = setup_plugin_options(pluginname, pluginclass)
    plugin = pluginclass(streamlink, resolved_url, options)
    log.info(f"Found matching plugin {pluginname} for URL {url}")

    if retry_max or retry_streams:
        retry_streams = 1
        retry_max = 0
        if retry_streams:
            retry_streams = retry_streams
        if retry_max:
            retry_max = retry_max
        streams = fetch_streams_with_retry(plugin, retry_streams, retry_max)
    else:
        streams = fetch_streams(plugin)

    if not streams:
        raise Exception(f"No playable streams found on this URL: {url}")

    if default_stream and not stream and not json:
        stream = default_stream

    if stream:
        validstreams = format_valid_streams(plugin, streams)
        for stream_name in stream:
            if stream_name in streams:
                log.info(f"Available streams: {validstreams}")
                handle_stream(plugin, streams, stream_name)
                return

        errmsg = f"The specified stream(s) '{', '.join(stream)}' could not be found"
        if not json:
            raise Exception(f"{errmsg}.\n       Available streams: {validstreams}")
        console.msg_json(
            plugin=plugin.module,
            metadata=plugin.get_metadata(),
            streams=streams,
            error=errmsg,
        )
        raise Exception()
    elif json:
        console.msg_json(
            plugin=plugin.module,
            metadata=plugin.get_metadata(),
            streams=streams,
        )
    elif stream_url:
        try:
            console.msg(streams[list(streams)[-1]].to_manifest_url())
        except TypeError:
            raise Exception(
                "The stream specified cannot be translated to a URL"
            ) from None
    else:
        validstreams = format_valid_streams(plugin, streams)
        console.msg(f"Available streams: {validstreams}")


def main():
    setup_streamlink()
    setup_plugins()

    streams = requests.get("https://www.reddit.com/r/soccerstreams/").text

    handle_url()
