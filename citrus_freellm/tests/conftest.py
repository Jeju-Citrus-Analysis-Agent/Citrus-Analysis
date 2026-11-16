import os

# Tests must not depend on a developer's .env key or call a paid model.
os.environ.setdefault('CITRUS_LOCAL_ONLY', '1')
