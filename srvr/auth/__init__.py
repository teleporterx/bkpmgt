# auth/__init__.py

# docstring
"""
Authentication module for handling JWT tokens.
"""

from .routes import auth_router
from .tokens import create_access_token, verify_access_token

__version__ = "1.0.0"