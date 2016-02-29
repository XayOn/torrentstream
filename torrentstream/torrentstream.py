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


async def play_file(*args):
    """
        Launch player against file
        player is adquired from the PLAYER environment variable
    """
    file = args[1]
    await asyncio.sleep(5)
    player = os.getenv('PLAYER')
    process = await asyncio.create_subprocess_exec(player, file.path)
    await process.wait()


async def server_stream(loop, file):
    """
        This is a simple example for the streaming coroutine required
        by stream_torrent.

        You can actually use this, it'll launch a local server and
        print out as debug messages the URLs of the stream

        After that, if PLAYER env variable is available, it'll launch
        subprocess.Popen(PLAYER, file) using ``play_file``
    """
    app = web.Application()
    app.router.add_static("/streams/", pathlib.Path('.').absolute())
    file_url = "http://localhost:8080/streams/{}".format(file.path)
    await asyncio.gather(play_file(file=file_url),
                         loop.create_server(app.make_handler(),
                                            '0.0.0.0', 8080))


def first_file(files):
    """ Get first file"""
    return files[0]


async def _stream_torrent(loop, magnet_link, stream_func, filter_func,
                          **kwargs):
    torrent = Torrent(magnet_link, kwargs, (6881, 6891))

    with asyncio.timeout(5 * 60):
        while not torrent.started:
            await asyncio.sleep(5)

    #: Secuential download.
    torrent.handle.set_sequential_download(True)

    #: Filter function must make sure to be precise...
    #: It gets a list of torrent.file
    playable_tfile = torrent.download_only(filter_func(torrent.files))

    if not playable_tfile:
        raise Exception("Could not find a playable source that matches"
                        " filter function")

    try:
        with asyncio.timeout(5 * 60):
            while True:
                LOG.debug("Got: %s", playable_tfile.completed_percent)
                if playable_tfile.completed_percent >= 5:
                    break
                await asyncio.sleep(5)
    except asyncio.TimeoutError:
        raise Exception('Could not get playable source in time')

    #: Parallel launch stream function and wait for completion from now on
    #: We'll forget the torrent itself and relie
    await asyncio.gather(wait_for_completion(torrent),
                         stream_func(loop, playable_tfile))

def stream_torrent(magnet_link, stream_func, filter_func, **kwargs):
    """ Stream torrent"""
    loop = asyncio.get_event_loop()
    loop.run_until_complete(_stream_torrent(loop, magnet_link,
                                            stream_func, filter_func,
                                            **kwargs))
    loop.run_forever()
    loop.close()
