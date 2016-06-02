#!/usr/bin/env python3

import queue
import requests
import threading
import logging
import logging.handlers
import time
import configparser
from colorlog import ColoredFormatter
from lxml import html


class PastebinScraper(object):
    def __init__(self):
        # TODO: Resilient requests import
        # TODO: DB connector

        # Read and split config
        self.config = configparser.ConfigParser()
        self.config.read('settings.ini')
        self.conf_general = self.config['GENERAL']
        self.conf_logging = self.config['LOGGING']
        self.conf_stdout = self.config['STDOUT']
        self.conf_file = self.config['FILE']

        # Internals
        self.unlimited_pastes = self.conf_general.getint('PasteLimit') == 0
        self.pastes = queue.Queue(maxsize=8)
        self.pastes_seen = set()

        # Init the logger
        self.logger = logging.getLogger('pastebin-scraper')
        self.logger.setLevel(logging.DEBUG)

        # Set up log rotation
        rotation = logging.handlers.RotatingFileHandler(
            filename=self.conf_logging['RotationLog'],
            maxBytes=self.conf_logging.getint('MaxRotationSize'),
            backupCount=self.conf_logging.getint('RotationBackupCount')
        )
        rotation.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s|%(levelname)-8s| %(message)s')
        rotation.setFormatter(formatter)
        self.logger.addHandler(rotation)

        console = logging.StreamHandler()
        console.setLevel(logging.INFO)
        formatter = ColoredFormatter(
            '%(log_color)s%(asctime)s|[%(levelname)-4s] %(message)s%(reset)s', '%H:%M:%S'
        )
        console.setFormatter(formatter)
        self.logger.addHandler(console)

    def _get_paste_data(self):
        paste_limit = self.conf_general.getint('PasteLimit')
        pb_link = self.conf_general['PBLINK']
        paste_counter = 0
        self.logger.info('Unlimited pastes detected' if self.unlimited_pastes
                         else 'Paste limit: ' + str(paste_limit))

        while self.unlimited_pastes or (paste_counter < paste_limit):
            page = requests.get(pb_link)
            self.logger.debug('Got {} - {} from {}'.format(
                page.status_code,
                page.reason,
                pb_link
            ))
            tree = html.fromstring(page.content)
            pastes = tree.cssselect('ul.right_menu li')
            for paste in pastes:
                if not self.unlimited_pastes \
                   and (paste_counter >= paste_limit):
                    # Break for limits % 8 != 0
                    break
                name_link = paste.cssselect('a')[0]
                name = name_link.text_content()
                href = name_link.get('href')[1:]  # Get rid of leading /
                data = paste.cssselect('span')[0].text_content().split('|')
                language = None
                if len(data) == 2:
                    # Got language
                    language = data[0]
                paste_data = (name, language, href)
                self.logger.debug('Paste scraped: ' + str(paste_data))
                if paste_data[2] not in self.pastes_seen:
                    # New paste detected
                    self.logger.debug('Scheduling new paste:' + str(paste_data))
                    self.pastes_seen.add(paste_data[2])
                    self.pastes.put(paste_data)
                    delay = self.conf_general.getint('NewPasteCheckInterval')
                    time.sleep(delay)
                    paste_counter += 1
                    self.logger.debug('Paste counter now at ' + str(paste_counter))

    def _download_paste(self):
        while True:
            p = self.pastes.get()  # (name, lang, href)
            self.logger.debug('Fetching raw paste %s...' % p[2])
            link = self.conf_general['PBLink'] + 'raw/' + p[2]
            data = requests.get(link)
            self.logger.debug('Fetched {} with {} - {}'.format(
                link,
                data.status_code,
                data.reason
            ))
            if 'requesting a little bit too much' in data:
                throttle_time = self.conf_general.getint('RequestThrottleTime')
                self.logger.info('Throttling detected - waiting %ss' % throttle_time)
                self.pastes.put(p)
                time.sleep(throttle_time)
            else:
                output = ''
                if self.conf_stdout.getboolean('ShowName'):
                    output += 'Name: %s\n' % p[0]
                if self.conf_stdout.getboolean('ShowLang'):
                    output += 'Lang: %s\n' % p[1]
                if self.conf_stdout.getboolean('ShowLink'):
                    output += 'Link: %s\n' % self.conf_general['PBLink'] + p[2]
                if self.conf_stdout.getboolean('ShowData'):
                    encoding = self.conf_stdout['DataEncoding']
                    limit = self.conf_stdout.getint('ContentDisplayLimit')
                    if limit > 0:
                        output += '\n\n%s' % data.content.decode(encoding)[:limit]
                    else:
                        output += '\n\n%s' % data.content.decode(encoding)
                print(output)

    def run(self):
        for i in range(self.conf_general.getint('DownloadWorkers')):
            t = threading.Thread(target=self._download_paste)
            t.setDaemon(True)
            t.start()
        s = threading.Thread(target=self._get_paste_data)
        s.start()
        s.join()


if __name__ == '__main__':
    ps = PastebinScraper()
    ps.run()
