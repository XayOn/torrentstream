# -*- coding: utf-8 -*-
"""
    Torrentstream
"""
import logging
import asyncio
from . torrent import wait_for_completion

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger(__name__)

__author__ = 'David Francos Cuartero'
__email__ = 'dfrancos@buguroo.com'
__version__ = '0.1.0'


TIMEOUT_CACHE_FILL = 5 * 60
TIMEOUT_START = 10 * 60
PERCENT_CACHE = 5


async def stream_torrent(loop, torrent, stream_func, filter_func):
    """
        Stream torrent.
        This will launch:
            - A logger to log torrent alerts (while torrent is downloading)
            - Torrent download
            - Once torrent.started, will try to find a playable file, and
              fill a ``PERCENT_CACHE`` cache to start playing

    """

    async def alert_watcher(torrent):
        """ Watch and log torrent alerts from LT """
        while not torrent.finished:
            alert = torrent.session.pop_alert()
            if alert:
                LOG.info(alert)
            await asyncio.sleep(1)

    # Force sequential mode
    torrent.sequential(True)

    # Start alert watcher task
    loop.create_task(alert_watcher(torrent))

    # If we're actually re-asking for a torrent, just relaunch streaming
    if torrent.finished:
        return [wait_for_completion(torrent),
                stream_func(loop, filter_func(torrent.files))]

    # Otherwise, wait for torrent to start or finish in TIMEOUT_START+
    # seconds
    with asyncio.timeout(TIMEOUT_START):
        while not torrent.started and not torrent.finished:
            await asyncio.sleep(5)

    # Only download filtered file
    playable_tfile = torrent.download_only(await filter_func(torrent.files))

    # If filter matches nothing, stop
    if not playable_tfile:
        raise Exception("Could not find a playable source that matches"
                        " filter function")

    # Try to fill the cache, if it's not filled within the first
    # ``TIMEOUT_CACHE_FILL`` seconds, exit
    with asyncio.timeout(TIMEOUT_CACHE_FILL):
        while playable_tfile.completed_percent < PERCENT_CACHE:
            await asyncio.sleep(5)

    return await asyncio.gather([wait_for_completion(torrent),
                                 stream_func(loop, playable_tfile)])
