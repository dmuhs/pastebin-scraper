#!/usr/bin/env python3

import queue
import random
import requests
import time
from lxml import html


class CheckableQueue(queue.Queue):
    def __contains__(self, item):
        with self.mutex:
            return item in self.queue


class PastebinScraper(object):
    def __init__(self):
        # TODO: Paste limit
        # TODO: DB connector
        self.PB_LINK = 'http://pastebin.com/'
        self.pastes = CheckableQueue(maxsize=10)
        self.paste_counter = 0

    def _parse_page_content(self):
        # TODO: Make import more resilient
        # TODO: page.status_code + page.reason
        page = requests.get(self.PB_LINK)
        tree = html.fromstring(page.content)
        return tree.cssselect('ul.right_menu li')

    def _get_paste_data(self):
        pastes = self._parse_page_content()
        for paste in pastes:
            name_link = paste.cssselect('a')[0]
            name = name_link.text_content()
            href = name_link.get('href')[1:]  # Get rid of leading /
            data = paste.cssselect('span')[0].text_content().split('|')
            language = None
            if len(data) == 2:
                # Got language
                language = data[0]
            paste_data = (name, language, href)
            if paste_data not in self.pastes:
                # New paste detected
                self.pastes.put(paste_data)
                self.paste_counter += 1
                delay = random.randrange(1, 5)
                time.sleep(delay)

    def _download_paste(self):
        while True:
            paste = self.pastes.get()  # (name, lang, href)
            data = requests.get(self.PB_LINK + 'raw/' + paste[2])
            if 'requesting a little bit too much' in data:
                print('Throttling...')
                self.pastes.put(paste)
                time.sleep(0.1)
            else:
                print('Name: {name}\nLanguage: {lang}\nLink:{link}\n{data}'.format(
                    name=paste[0],
                    lang=paste[1],
                    link=paste[2],
                    data=data
                ))

    def run(self):
        pass


if __name__ == '__main__':
    ps = PastebinScraper()
    ps.run()
