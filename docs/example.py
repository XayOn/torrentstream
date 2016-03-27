"""
    Example use of torrentstream and pychapter combined
"""
from contextlib import suppress
import asyncio
import pathlib
import aiohttp
from aiohttp import web
from torrentstream import _stream_torrent
from pychapter import Chapter


class PyChapterAPI(web.View):
    """ Main API """

    @property
    def chapter(self):
        """ Get chapter from match_info"""
        with suppress(KeyError):
            magnet = self.request.match_info['magnet']

        if not magnet:
            title = self.request.match_info['series']
            season = self.request.match_info['season']
            episode = self.request.match_info['chapter']
            chapter = Chapter(title=title, episode=episode, season=season)
        else:
            chapter = Chapter(magnet=magnet)

        if chapter.filename in self.request.app:
            raise aiohttp.web.HTTPFound(self.request.app[chapter.filename]['url'])

    async def get(self):
        """ Get a chapter stream. Will redirect once chapter is ready """
        chapter = self.chapter
        file, awaitable = chapter.file.get()

        file_url = "http://localhost:8080/streams/{}".format(file.path)

        self.request.app[chapter.filename] = {
            'cancelable': asyncio.ensure_future(awaitable),
            'url': file_url
        }
        raise aiohttp.web.HTTPFound(file_url)

    async def delete(self):
        """ Cancels the torrent download """
        chapter = self.chapter
        if chapter.filename in self.request.app:
            self.request.app[chapter.filename]['cancelable'].cancel()
            return web.Response(text="OK")

        raise aiohttp.web.HTTPNotFound()


def server():
    """ Main server """
    app = web.Application()
    app.router.add_route('*', '/get/{series}/{season}/{chapter}', PyChapterAPI)
    app.router.add_route('*', '/get/{magnet}', PyChapterAPI)
    app.router.add_static("/streams/", pathlib.Path('.').absolute())
    web.run_app(app)


if __name__ == "__main__":
    server()
