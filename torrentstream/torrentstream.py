# -*- coding: utf-8 -*-
import logging
import asyncio
from . torrent import Torrent

logging.basicConfig(level=logging.DEBUG)
LOG = logging.getLogger(__name__)

async def _stream_torrent(loop, magnet_link, stream_func, filter_func,
                          **kwargs):

    torrent = Torrent(magnet_link, kwargs, (6881, 6891))

    with asyncio.timeout(5 * 60):
        while not torrent.started:
            await asyncio.sleep(5)

    #: Filter function must make sure to be precise...
    torrent.download_only(filter_func(torrent.files))

    try:
        with asyncio.timeout(5 * 60):
            while True:
                file = torrent.files[playable_file]
                if file['completed_percent'] >= 5:
                    break
                await asyncio.sleep(5)
    except asyncio.TimeoutError:
        raise Exception('Could not get playable source in time')

    # LOOP. : # Add a coroutine that'll be called with a filelike object
    # For the specified file
    while not torrent.finished:
        await asyncio.sleep(5)


def stream_torrent(magnet_link, stream_func, filter_func, **kwargs):

    LOOP = asyncio.get_event_loop()
    LOOP.run_until_complete(_stream_torrent(LOOP, magnet_link, stream_func,
                            filter_func, **kwargs))
    LOOP.run_forever()
    LOOP.close()
