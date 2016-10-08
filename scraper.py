#!/usr/bin/env python3

import logging
import logging.handlers
import os
import sys
import threading
import time
from datetime import datetime
from os import path

import requests
from lxml import html

import configparser
is_py2 = sys.version[0] == '2'
if is_py2:
    import Queue as queue
else:
    import queue as queue
from colorlog import ColoredFormatter


class PasteDBConnector(object):
    supported = ('MYSQL', 'SQLITE')

    def __init__(self, db, **kwargs):
        try:
            self.logger = logging.getLogger('pastebin-scraper')
            from sqlalchemy.ext.declarative import declarative_base
        except ImportError:
            self.logger.error('SQLAlchemy import failed. Make sure the SQLAlchemy Python library '
                              'is installed! To check your existing installation run: '
                              'python3 -c "import sqlalchemy;print(sqlalchemy.__version__)"')
        if db not in self.supported:
            msg = 'The specified database %s is not supported. Please chose an engine from %s' % \
                  (db, ', '.join(self.supported))
            self.logger.error(msg)
            raise ValueError(msg)
        self.db = db
        self.Base = declarative_base()
        self.engine = self._get_db_engine(**kwargs)
        self.session = self._get_db_session(self.engine)
        self.paste_model = self._get_paste_model(self.Base, **kwargs)
        self.Base.metadata.create_all(self.engine)

    def _get_db_engine(self, **kwargs):
        from sqlalchemy import create_engine
        if self.db == 'MYSQL':
            # use the mysql-python connector
            location = 'mysql+pymysql://'
            location += '{username}:{password}@{host}:{port}'.format(
                host=kwargs.pop('host'),
                port=kwargs.pop('port'),
                username=kwargs.pop('username'),
                password=kwargs.pop('password'),
            )
            location += '/{table_name}?charset={charset}'.format(
                table_name=kwargs.pop('table_name'),
                charset='utf8'
            )
            self.logger.info('Using MySQL at ' + location)
            return create_engine(location)
        elif self.db == 'SQLITE':
            location = 'sqlite+pysqlite:///' + kwargs.pop('filename')
            self.logger.info('Using SQLite at ' + location)
            return create_engine(location)

    def _get_db_session(self, engine):
        from sqlalchemy.orm import sessionmaker
        return sessionmaker(bind=engine)()

    def _get_paste_model(self, base, **kwargs):
        db = self.db

        from sqlalchemy import Column, Integer, String, DateTime
        if db == 'MYSQL':
            from sqlalchemy.dialects.mysql import LONGTEXT
        elif db == 'SQLITE':
            from sqlalchemy import UnicodeText

        class Paste(base):
            __tablename__ = kwargs.pop('table_name')

            id = Column(Integer, primary_key=True)
            name = Column('name', String(60))
            lang = Column('language', String(30))
            link = Column('link', String(28))  # Assuming format http://pastebin.com/XXXXXXXX
            date = Column('date', DateTime())
            if db == 'MYSQL':
                data = Column('data', LONGTEXT(charset='utf8'))
            else:
                data = Column('data', UnicodeText())

            def __repr__(self):
                return "<Paste(id=%s, name='%s', lang='%s', link='%s', date='%s', data='%s')" %\
                       (self.id,
                        self.name,
                        self.lang,
                        self.link,
                        str(self.date),
                        self.data[:10])

        return Paste

    def add(self, paste, data):
        model = self.paste_model(
            name=paste[0],
            lang=paste[1],
            link=paste[2],
            date=datetime.now(),
            data=data.content.replace(b'\\', b'\\\\').decode('unicode-escape')
        )
        self.logger.debug('Adding model ' + str(model))
        try:
            self.session.add(model)
            self.session.commit()
        except:
            self.logger.error(
                'An error occurred while adding a paste to %s: %s' %
                (self.db, sys.exc_info()[0])
            )


class PastebinScraper(object):
    def __init__(self):
        # Read and split config
        self.config = configparser.ConfigParser()
        self.config.read('settings.ini')
        self.conf_general = self.config['GENERAL']
        self.conf_logging = self.config['LOGGING']
        self.conf_stdout = self.config['STDOUT']
        self.conf_mysql = self.config['MYSQL']
        self.conf_sqlite = self.config['SQLITE']
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

        if not (self.conf_stdout.getboolean('Enable') or self.conf_mysql.getboolean('Enable')
                or self.conf_sqlite.getboolean('Enable') or self.conf_file.getboolean('Enable')):
            self.logger.error('No output method specified! Please set at least one output method '
                              'in the settings.ini to \'yes\'.')
            raise RuntimeError('No output method specified!')

        # Create File output folder if needed
        if not path.exists('output') and self.conf_file.getboolean('Enable'):
            self.logger.debug('Creating new output directory')
            os.mkdir('output')

        # DB connectors if needed
        self.mysql_conn = None
        self.sqlite_conn = None
        if self.conf_mysql.getboolean('Enable'):
            self.logger.debug('Initializing MySQL connector')
            self.mysql_conn = PasteDBConnector(
                db='MYSQL',
                host=self.conf_mysql['Host'],
                port=self.conf_mysql['Port'],
                username=self.conf_mysql['Username'],
                password=self.conf_mysql['Password'],
                table_name=self.conf_mysql['TableName']
            )
        if self.conf_sqlite.getboolean('Enable'):
            self.logger.debug('Initializing SQLite connector')
            self.sqlite_conn = PasteDBConnector(
                db='SQLITE',
                filename=self.conf_sqlite['Filename'],
                table_name=self.conf_sqlite['TableName']
            )

    def _get_paste_data(self):
        paste_limit = self.conf_general.getint('PasteLimit')
        pb_link = self.conf_general['PBLINK']
        paste_counter = 0
        self.logger.info('No scrape limit set - scraping indefinitely' if self.unlimited_pastes
                         else 'Paste limit: ' + str(paste_limit))

        while self.unlimited_pastes or (paste_counter < paste_limit):
            page = self._handle_data_download(pb_link)

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
                name = name_link.text_content().strip()
                href = name_link.get('href')[1:]  # Get rid of leading /
                data = paste.cssselect('span')[0].text_content().split('|')
                language = None
                if len(data) == 2:
                    # Got language
                    language = data[0].strip()
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
                    if paste_counter % 100 == 0:
                        self.logger.info('Scheduled %d pastes' % paste_counter)

    def _download_paste(self):
        while True:
            paste = self.pastes.get()  # (name, lang, href)
            self.logger.debug('Fetching raw paste ' + paste[2])
            link = self.conf_general['PBLink'] + 'raw/' + paste[2]
            data = self._handle_data_download(link)

            self.logger.debug('Fetched {} with {} - {}'.format(
                link,
                data.status_code,
                data.reason
            ))
            if self.conf_stdout.getboolean('Enable'):
                self._write_to_stdout(paste, data)
            if self.conf_mysql.getboolean('Enable'):
                self._write_to_mysql(paste, data)
            if self.conf_file.getboolean('Enable'):
                self._write_to_file(paste, data)
            if self.conf_sqlite.getboolean('Enable'):
                self._write_to_sqlite(paste, data)

    def _handle_data_download(self, link):
        while True:
            try:
                data = requests.get(link)
            except:
                retry = self.conf_general.getint('ConnectionRetryInterval')
                self.logger.debug(
                    'Error connecting to %s: Retry in %ss, TRACE: %s' %
                    (link, retry, sys.exc_info())
                )
                self.logger.info('Connection problems - trying again in %ss' % retry)
                time.sleep(retry)
            else:
                if data.status_code == 403 and b'Pastebin.com has blocked your IP' in data.content:
                    self.logger.info('Our IP has been blocked. Trying again in an hour.')
                    time.sleep(self.conf_general.getint('IPBlockedWaitTime'))
                return data

    def _assemble_output(self, conf, paste, data):
        output = ''
        if conf.getboolean('ShowName'):
            output += 'Name: %s\n' % paste[0]
        if conf.getboolean('ShowLang'):
            output += 'Lang: %s\n' % paste[1]
        if conf.getboolean('ShowLink'):
            output += 'Link: %s\n' % (self.conf_general['PBLink'] + paste[2])
        if conf.getboolean('ShowData'):
            encoding = conf['DataEncoding']
            limit = conf.getint('ContentDisplayLimit')
            if limit > 0:
                output += '\n%s\n\n' % data.content.decode(encoding)[:limit]
            else:
                output += '\n%s\n\n' % data.content.decode(encoding)
        return output

    def _write_to_stdout(self, paste, data):
        output = self._assemble_output(self.conf_stdout, paste, data)
        sys.stdout.write(output)

    def _write_to_mysql(self, paste, data):
        self.mysql_conn.add(paste, data)

    def _write_to_sqlite(self, paste, data):
        self.sqlite_conn.add(paste, data)

    def _write_to_file(self, paste, data):
        # Date and paste ID
        fname = '%s_%s.txt' % (datetime.now().strftime('%Y-%m-%d.%H-%M-%S'), paste[2])
        with open(path.join('output', fname), 'w') as f:
            output = self._assemble_output(self.conf_file, paste, data)
            f.write(output)

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
