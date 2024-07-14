# CzSkY

![OrionDss](https://user-images.githubusercontent.com/2523097/195431903-615c48f6-4268-4441-bf66-7120a29319fa.png)

## Prerequisites 

Before running this project, install `libicu-dev`, which provides International Components for Unicode libraries. Below are installation steps for various operating systems.

### Linux

For Debian-based distributions like Ubuntu:

```sh
sudo apt-get update
sudo apt-get install -y libicu-dev
```

For Red Hat-based distributions like CentOS or Fedora:

```sh
sudo yum install libicu-devel
```

### Windows

Using Chocolatey:

1.Install Chocolatey if you haven't already.
2.Run:
```sh
choco install icu4c
```

Using vcpkg:

1.Install vcpkg if you haven't already.
2.Run:

```sh
vcpkg install icu
vcpkg integrate install
```

### macOS

Using Homebrew:

1.Install Homebrew if you haven't already.
2.Run:

```sh
brew install icu4c
```

## Setting up

##### Clone the repository

```
$ git clone https://github.com/skybber/czsky.git
$ cd czsky
```

##### Initialize a virtual environment

Linux:
```
$ python3 -m venv venv; source venv/bin/activate
```

Windows:
```
$ python3 -m venv venv
$ venv\Scripts\activate.bat
```

Unix/MacOS:
```
$ python3 -m venv venv
$ source venv/bin/activate
```
Learn more in [the documentation](https://docs.python.org/3/library/venv.html#creating-virtual-environments).

Note: if you are using a python before 3.3, it doesn't come with venv. Install [virtualenv](https://docs.python-guide.org/dev/virtualenvs/#lower-level-virtualenv) with pip instead.

##### (If you're on a Mac) Make sure xcode tools are installed

```
$ xcode-select --install
```

##### Add Environment Variables

Create a file called `config.env` that contains environment variables. **Very important: do not include the `config.env` 
file in any commits. This should remain private.** You will manually maintain this file locally, and keep it in sync on your host.
To make it easy to set up this file with the required values, you can use config.env.example as a configuration template.

Variables declared in file have the following format: `ENVIRONMENT_VARIABLE=value`. You may also wrap values in double quotes like `ENVIRONMENT_VARIABLE="value with spaces"`.

1. In order for Flask to run, there must be a `SECRET_KEY` variable declared. Generating one is simple with Python 3:

   ```
   $ python3 -c "import secrets; print(secrets.token_hex(16))"
   ```

   This will give you a 32-character string. Copy this string and add it to your `config.env`:

   ```
   SECRET_KEY=Generated_Random_String
   ```

2. The mailing environment variables can be set as the following.
   We recommend using [Sendgrid](https://sendgrid.com) for a mailing SMTP server, but anything else will work as well.

   ```
   MAIL_USERNAME=SendgridUsername
   MAIL_PASSWORD=SendgridPassword
   ```

Other useful variables include:

| Variable        | Default   | Discussion  |
| --------------- |-------------| -----|
| `ADMIN_EMAIL`   | `flask-base-admin@example.com` | email for your first admin account |
| `ADMIN_PASSWORD`| `password`                     | password for your first admin account |
| `DATABASE_URL`  | `data-dev.sqlite`              | Database URL. Can be Postgres, sqlite, etc. |
| `REDISTOGO_URL` | `http://localhost:6379`        | [Redis To Go](https://redistogo.com) URL or any redis server url |
| `RAYGUN_APIKEY` | `None`                         | API key for [Raygun](https://raygun.com/raygun-providers/python), a crash and performance monitoring service |
| `FLASK_CONFIG`  | `default`                      | can be `development`, `production`, `default`, `heroku`, `unix`, or `testing`. Most of the time you will use `development` or `production`. |


##### Install the dependencies

```
$ pip install -r requirements.txt
```

##### Other dependencies for running locally

You need [Redis](http://redis.io/), and [Sass](http://sass-lang.com/). Chances are, these commands will work:


**Sass:**

```
$ gem install sass
```

**Redis:**

_Mac (using [homebrew](http://brew.sh/)):_

```
$ brew install redis
```

_Linux:_

```
$ sudo apt-get install redis-server
```


##### Initialize CzSkY project

```
$ ./recreate_all.sh
```

## Running CzSkY

```
$ source venv/bin/activate
$ honcho start -e config.env -f Local
```

#### Opening CzSkY in Browser
To open the CzSkY home page in your browser, navigate to `http://localhost:5000`.

#### External Access
To enable access from an external computer, run CzSkY on all network devices. Modify the appropriate line in the `Local` file as follows:

#### Additional Catalogs of Stars Up to 17 Magnitude
To add extra catalogs of stars from **Stellarium**, download the catalogs in Stellarium and locate their storage directory (for Linux, this is `~/.stellarium/stars/default`). Finally copy the downloaded catalogs to the `data/` directory in the CzSkY project.

```plaintext
[Provide the exact line to modify with detailed instructions here]
```


```
web: flask --debug --app manage run --host=0.0.0.0 --port=5000 
```

For Windows users having issues with binding to a redis port locally, refer to [this issue](https://github.com/hack4impact/flask-base/issues/132).

