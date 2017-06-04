## pastebin-scraper

This is a multithreaded scraping script for [Pastebin](http://pastebin.com/). It scrapes the main site for new pastes, downloads their raw content and processes them by a user-defined output format.

### WHY?
Fun.

### Installation
The usual dance.
```
pip install -r requirements.txt
```

Define all required specs in `settings.ini`. Should you decide to go with a database output, make sure the respective connector is installed. At the moment MySQL with `pymysql` and SQLite with the standard built in Python 3 connector are supported.

Also note that the file output creates a subdirectory `output` and dumps every paste as a separate file into it.

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
- `TableName` Main table name to insert data into
- `Host` MySQL server host
- `Port` MySQL server port
- `Username` MySQL server user
- `Password` User password

#### SQLITE
- `Enable` Enable SQLite output
- `Filename` Filename the db should be saved as (usually ends with .db)
- `TableName` Main table name to insert data into

---

If you use this thing for some cool data analysis or even research, let me know if I can help!

Inspiration for this scraper was taken from [here](http://www.michielovertoom.com/python/pastebin-abused/).
