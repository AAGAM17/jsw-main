# install_nltk.py
import nltk
import ssl
import warnings

# Suppress SSL warnings
warnings.filterwarnings("ignore", category=UserWarning)

# Bypass SSL verification
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

# Download punkt with clean context
nltk.download('punkt', quiet=True)