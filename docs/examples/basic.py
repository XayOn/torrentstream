from torrentstream import Torrent, stream_torrent
import asyncio

async def sample_stream_torrent(magnet_link, stream_func, filter_func):
    """ Stream torrent"""

    def first_file(files):
        """ Get first file"""
        return files[0]

    async def server_stream(loop, file):
        """
            Runs a simple web server with aiohttp that exposes
            the specified file.

            As this runs as a callback from _stream_torrent
            it'll be ready to play when it starts.

            Remember that this is just an example and should not
            be used as production code
        """

        async def play_file(loop, file):
            """
                Launch player against file
                player is adquired from the PLAYER environment variable
            """
            LOG.info(file.__dict__)
            player = os.getenv('PLAYER')
            if player:
                process = await asyncio.create_subprocess_exec(
                    player, file.path)
                await process.wait()
            return

    app = web.Application()
    app.router.add_static("/streams/", pathlib.Path('.').absolute())
    LOG.info("http://localhost:8080/streams/{}".format(file.path))

    await asyncio.gather(play_file(loop, file),
                         loop.create_server(app.make_handler(),
                                            '0.0.0.0', 8080))




torrent = Torrent(magnet, {}, (randint(1024, 2000), randint(1024, 2000)))
loop = asyncio.get_event_loop()
loop.run_until_complete(stream_torrent(
    loop, torrent, server_stream, first_file))
loop.close()



