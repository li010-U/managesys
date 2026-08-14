"""Dev-tools safety guard.

These scripts write directly to the database (raw sqlite3 / HTTP to localhost)

and are meant ONLY for generating demo/scratch data during development.



Running them against a live database can corrupt real data. To run any of them

deliberately, set the environment variable ALLOW_DEV_TOOL_WRITE=1.

"""

import os

import sys





def ensure_dev_mode():

    if os.environ.get("ALLOW_DEV_TOOL_WRITE") != "1":

        sys.stderr.write(

            "[!] Blocked by dev-tools guard: these scripts write directly to the "

            "database and may corrupt production data.\n"

            "[!] To run deliberately: set ALLOW_DEV_TOOL_WRITE=1 .\n"

        )

        sys.exit(1)

