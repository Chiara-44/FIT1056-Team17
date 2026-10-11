# Lets pytest find the "app" package when run from the project folder.
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
