# -*- coding: utf-8 -*-
"""
    Torrentstream
"""
import logging
import asyncio
from aiohttp import web
import os
import pathlib
from . torrent import Torrent, wait_for_completion

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger(__name__)

__author__ = 'David Francos Cuartero'
__email__ = 'dfrancos@buguroo.com'
__version__ = '0.1.0'


async def _stream_torrent(loop, torrent, stream_func, filter_func):
    """
        Stream torrent
    """
    async def alert_watcher(torrent):
        """ Watch and log torrent alerts from LT """
        while True:
            alert = torrent.session.pop_alert()
            if alert:
                LOG.info(alert)
            await asyncio.sleep(1)

    loop.create_task(alert_watcher(torrent))

    if torrent.finished:
        return [wait_for_completion(torrent),
                stream_func(loop, filter_func(torrent.files))]

    with asyncio.timeout(10 * 60):  #: TODO Make this timeout configurable
        while not torrent.started and not torrent.finished:
            await asyncio.sleep(5)

    self.sequential(True)

    playable_tfile = torrent.download_only(await filter_func(torrent.files))
    LOG.info("Found playable file: %s", playable_tfile)

    if not playable_tfile:
        raise Exception("Could not find a playable source that matches"
                        " filter function")

    try:
        with asyncio.timeout(5 * 60):
            while True:
                if playable_tfile.completed_percent >= 5:
                    break
                await asyncio.sleep(5)
    except asyncio.TimeoutError:
        raise Exception('Could not get playable source in time')

    return await asyncio.gather([wait_for_completion(torrent),
            stream_func(loop, playable_tfile)]
