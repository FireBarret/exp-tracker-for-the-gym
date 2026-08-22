# PythonAnywhere WSGI config template.
#
# On the Web tab, click the "WSGI configuration file" link, delete everything in
# the editor that opens, and paste this in -- with YOUR_USERNAME replaced.
#
# Nothing else is needed here: app.py loads GYM_APP_PASSWORD and FLASK_SECRET_KEY
# from the .env file sitting next to it.

import sys

project_home = "/home/YOUR_USERNAME/exp-tracker-for-the-gym"
if project_home not in sys.path:
    sys.path.insert(0, project_home)

from app import app as application
