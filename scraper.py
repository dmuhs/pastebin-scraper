#!/usr/bin/env python3

import requests
from lxml import html


class PastebinScraper(object):
    def __init__(self):
        # TODO: Paste limit
        # TODO: DB connector
        self.PB_LINK = 'http://pastebin.com/'

    def _parse_page_content(self):
        # TODO: Make import more resilient
        # TODO: page.status_code + page.reason
        page = requests.get(self.PB_LINK)
        tree = html.fromstring(page.content)
        return tree.cssselect('ul.right_menu li')

    def _scrape_pastes(self):
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
            yield (name, language, self.PB_LINK + href)

    def _output_pastes(self):
        # TODO: Output in sys.stdout, MySQL
        for p in self._scrape_pastes():
            print('Name: {name}\nLanguage: {lang}\nLink: {link}\n'.format(**{
                'name': p[0],
                'lang': p[1],
                'link': p[2]
            }))

    def run(self):
        self._output_pastes()


if __name__ == '__main__':
    ps = PastebinScraper()
    ps.run()
