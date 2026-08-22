# PythonAnywhere WSGI config template.
#
# On the Web tab, after "Add a new web app" -> Manual configuration -> Python 3.x,
# open the WSGI configuration file it links to and replace its contents with this,
# adjusting YOUR_USERNAME below. (You can also just copy this whole file's content in.)

import sys
import os

project_home = "/home/YOUR_USERNAME/exp-tracker-for-the-gym"
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# Load .env (GYM_APP_PASSWORD, FLASK_SECRET_KEY) if you're using python-dotenv locally
# on PythonAnywhere too; otherwise set these as real env vars in the Web tab instead.
os.environ.setdefault("GYM_APP_PASSWORD", "")  # or set via the Web tab's env vars section
os.environ.setdefault("FLASK_SECRET_KEY", "")

from app import app as application
