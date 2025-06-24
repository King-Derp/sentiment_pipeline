"""Top-level package initializer for the Reddit Scraper project.

This project historically ended up with a nested package structure:
    reddit_scraper/          (top-level package – entry-points & metadata)
    └── reddit_scraper/      (inner package – core implementation modules)

Many modules inside the inner package perform absolute imports such as
`from reddit_scraper.collector.backfill import BackfillRunner`.  When the
application is executed as `python -m reddit_scraper.reddit_scraper.cli`,
Python first imports the **outer** package (`reddit_scraper`).  Because the
outer package does *not* contain a `collector` sub-package, those absolute
imports fail with `ModuleNotFoundError` inside a Docker container.

To preserve the current directory layout while avoiding a large-scale
refactor, we dynamically expose the inner package’s sub-modules on the
outer package namespace at import time.  Effectively, importing e.g.
`reddit_scraper.collector` will be redirected to
`reddit_scraper.reddit_scraper.collector` under the hood.

This adapter should be executed *before* any inner-package modules are
imported, so placing it in `__init__.py` guarantees it runs first.
"""

from importlib import import_module
import pkgutil
import sys
from pathlib import Path

# Name of the inner package ("reddit_scraper.reddit_scraper")
_inner_pkg_name = __name__ + ".reddit_scraper"

try:
    _inner_pkg = import_module(_inner_pkg_name)
except ModuleNotFoundError:
    # Inner package not present – nothing to expose
    _inner_pkg = None

if _inner_pkg is not None:
    # Add the inner package's directory to this package's search path so that
    # standard import machinery can discover sub-packages (collector, scrapers, etc.)
    _inner_path = Path(_inner_pkg.__file__).parent
    if str(_inner_path) not in __path__:
        __path__.append(str(_inner_path))

    # Register the inner package itself as an alias so users can still access
    # `reddit_scraper.reddit_scraper` explicitly if they want.
    sys.modules.setdefault(f"{__name__}.reddit_scraper", _inner_pkg)


# Expose the inner package itself for completeness (allows
# `import reddit_scraper.reddit_scraper`)
sys.modules.setdefault(f"{__name__}.reddit_scraper", _inner_pkg)
