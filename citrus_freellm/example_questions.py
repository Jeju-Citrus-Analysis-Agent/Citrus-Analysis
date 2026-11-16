"""Keep the complete tool-category selector together under example questions."""
from .local_tools import TOOL_GUIDE

EXAMPLE_CATEGORIES = {title: questions for key, title, questions in TOOL_GUIDE if key != 'quality'}
