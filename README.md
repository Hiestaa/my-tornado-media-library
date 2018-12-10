# My Tornado Media Library

This tornado-based project offers a web interface to view, sort, tag and filter albums and videos.
This aims to offer advanced video analysis and compilation feature, but this is still a work in progress.

## Usage

### Windows

This project depends on several dependencies which aren't so easy to setup on a windows environment.
Notably, opencv, tensorflow and gpu counterpart as well as some binaries such as vlc and ffmpeg need
to be installed on the system.

To simplify the use, a fully portable and standalone archive is available here: #TODO.
The archive contains a full python environment, the necessary (portable) binaries and should work
right out of the box. Once extracted, simply run the file:

```
server.bat
```

You can then point any browser to `localhost:666` and start organizing your library.

A fully standalone version (embedding a chromium browser) is currently a work in progress,
but can be started with:

```
app.bat
```

### Linux & Mac OS X

On a unix-based environment where python is installed, simply run:

```
pip install -r requirements.txt
```

Then, start the server:

```
python src/server_main.py -vv
```

You should now be able to reach `localhost:666/` to start organizing your library.

Disclaimer: this project is developped and mainly tested on a windows environment.

A fully standalone version (embedding a chromium browser) is currently a work in progress,
but can be started with:

```
python src/main.py
```

#### Advanced Usage

The DeepFaceLab lib and its FaceLib component are used for video analysis and compilation.
These features won't work (#TODO: make them unavailable) if these aren't added to the repo in the `lib` folder.

The standalone torrent version designed for contains this library already. For linux/macosx usage,
this lib couldn't be added to the git repo because it contains a deep learning trained model which is 90MB+ on disk and wouldn't fit in a free github repo.

Please download the archive here: #TODO and extract in the `lib` folder.

## Structure

The source is organized as follow:

* `config/`: configuration file
* `experiments/`: contains standalone scripts used to experiment ideas before implementing them
* `http/assets/`: static assets served as is to the client. Contains javascript & css custom code and libraries
* `http/templates/`: tornado compatible html templates
* `server/`: deal with the servicing of http requests
* `server/services/`: services, deal with interacting with the database.
* `server/requestHandlers/`: handle requests for the actions supported by the application
* `tools/`: utilities and more advanced tools, contains notably the database updating process, the video analyzer and compiler.

