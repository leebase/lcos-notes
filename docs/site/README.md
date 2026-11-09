# Build the user handbook

The application does not depend on Python. Building this static documentation
site requires Python3 and Python-Markdown (`python3-markdown` on Debian/Devuan).

```sh
python3 docs/site/build.py --output /path/to/new/handbook-output
```

Output must be a new or empty directory. Serve it with any static web server or
open index.html locally. The downloadable ZIP includes all pages, local assets
and client-side search; it makes no external font/script/API requests.

Edit topic sources in ../handbook/, ordered by pages.json. The complete reference
is rendered directly from ../../DOCUMENTATION.md, avoiding a second copy to
maintain. Site generation changes no application code or package version.
The intended public location is /lcos-notes/ on the existing webroot host.
