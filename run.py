# main dir, create app via func in the package file
import os

from main import create_app

app = create_app(os.environ.get("APP_ENV"))
