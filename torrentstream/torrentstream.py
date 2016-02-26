# -*- coding: utf-8 -*-
import libtorrent as lt
import logging
import asyncio

logging.basicConfig(level=logging.DEBUG)
LT_SESSION = lt.session()
LT_SESSION.listen_on(6881, 6891)
LOOP = asyncio.get_event_loop()
LOG = logging.getLogger(__name__)


def get_files(handle, filter_function):
    return True


async def finish(handle):
    while handle.status().state != lt.torrent_status.seeding:
        await asyncio.sleep(5)


async def start(handle):
    while not handle.has_metadata():
        LOG.debug('Still getting metadata')
        await asyncio.sleep(5)


async def is_playable(handle):
    while True:
        await asyncio.sleep(5)


async def _stream_torrent(loop, magnet_link, stream_func, filter_func,
                          **kwargs):
    params = {
        'save_path': '.',
        'storage_mode': lt.storage_mode_t.storage_mode_sparse
    }
    params.update(kwargs)
    handle = lt.add_magnet_uri(LT_SESSION, magnet_link, params)

    with asyncio.timeout(5 * 60):
        await start(handle)

    with asyncio.timeout(5 * 60):
        await is_playable(handle)

    for file in get_files(handle, filter_function=filter_func):
        LOOP.call_soon(stream_func(file))

    await finish(handle)


def stream_torrent(magnet_link, stream_func, filter_func, **kwargs):
    LOOP.run_until_complete(_stream_torrent(LOOP, magnet_link, stream_func,
                            filter_func, **kwargs))
    LOOP.run_forever()
    LOOP.close()
