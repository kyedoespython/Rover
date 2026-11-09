# main dir, create app via func in the package file
from main import create_app
import os

app = create_app(os.environ.get("APP_ENV"))