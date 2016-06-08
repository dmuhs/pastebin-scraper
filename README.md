## pastebin-scraper

This is a multithreaded scraping script for [Pastebin](http://pastebin.com/). It scrapes the main site for new pastes, downloads their raw content and processes them by a user-defined output format.

### Installation
The usual dance.
```
pip install -r requirements.txt
```

Define all required specs in `settings.ini`. Should you decide to go with a database output, make sure the respective connector is installed. At the moment only MySQL with `pymysql` are supported.

### Settings
`ini` is a highly underrated file format. Here are some definitions on what the settings parameter actually do.

#### GENERAL
- `PasteLimit` Stop after having scraped n pastes. Set to 0 for indefinite scraping
- `PBLink` URL to Pastebin or another equivalent site
- `DownloadWorkers` Number of workers that download the raw paste content and further process it
-  `NewPasteCheckInterval` Time to wait before checking the main site for new pastes again
- `IPBlockedWaitTime` Time to wait until checking the main site again after the scraper's IP has been blocked

#### LOGGING
- `RotationLog` Location of log file that contains debug output
- `MaxRotationSize` Size in bytes before another log file is created
- `RotationBackupCount` Maximum number of log files to keep

#### STDOUT/ FILE
- `Enable` Enable formatted stdout output of paste data
- `ContentDisplayLimit` Maximum amount of characters to show before content is cut off (0 to display all)
- `ShowName` Display the paste name
- `ShowLang` Display the paste language
- `ShowLink` Display the complete paste link
- `ShowData` Display the raw paste content
- `DataEncoding` Encoding of the raw paste data

#### MYSQL
- `Enable` Enable MySQL output
- `DBName` Database name to insert data into
- `Host` MySQL server host
- `Port` MySQL server port
- `Username` MySQL server user
- `Password` User password

---

I hereby officially challenge [@DanAmador](https://github.com/danamador) to throw machine learning at this and build something cool!

Inspiration for this scraper was taken from [here](http://www.michielovertoom.com/python/pastebin-abused/).
