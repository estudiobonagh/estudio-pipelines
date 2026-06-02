"""Configuration loader — reads .env, validates, returns Settings."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv


class Settings:
    """Application settings loaded from environment variables.

    All timeouts and limits are configurable, not hardcoded.
    """

    def __init__(self) -> None:
        load_dotenv()

        # Twilio Sandbox
        self.TWILIO_ACCOUNT_SID: str = self._require("TWILIO_ACCOUNT_SID")
        self.TWILIO_AUTH_TOKEN: str = self._require("TWILIO_AUTH_TOKEN")
        self.TWILIO_WHATSAPP_NUMBER: str = self._require("TWILIO_WHATSAPP_NUMBER")

        # Grok (xAI)
        self.XAI_API_KEY: str = self._require("XAI_API_KEY")
        self.XAI_BASE_URL: str = os.getenv("XAI_BASE_URL", "https://api.x.ai/v1")
        self.XAI_MODEL: str = os.getenv("XAI_MODEL", "grok-4.3")

        # Google Drive
        creds_json = os.getenv("GOOGLE_DRIVE_CREDENTIALS_JSON", "")
        if creds_json:
            import json

            self.GOOGLE_DRIVE_CREDENTIALS: str | dict = json.loads(creds_json)
        else:
            self.GOOGLE_DRIVE_CREDENTIALS = self._require("GOOGLE_DRIVE_CREDENTIALS")
            self._validate_credentials_file()
        self.GOOGLE_DRIVE_CLIENTS_ID: str = self._require("GOOGLE_DRIVE_CLIENTS_ID")
        self.GOOGLE_DRIVE_INBOX_ID: str = os.getenv(
            "GOOGLE_DRIVE_INBOX_ID", ""
        )

        # Database
        self.DATABASE_PATH: str = os.getenv("DATABASE_PATH", "./data/processing.db")

        # Server
        self.HOST: str = os.getenv("HOST", "0.0.0.0")
        self.PORT: int = int(os.getenv("PORT", "8000"))

        # Limits
        self.MAX_FILE_SIZE_MB: int = int(os.getenv("MAX_FILE_SIZE_MB", "15"))
        self.CLASSIFICATION_TIMEOUT_S: int = int(
            os.getenv("CLASSIFICATION_TIMEOUT_S", "15")
        )

        # Validate credentials file exists
        self._validate_credentials_file()

    @staticmethod
    def _require(name: str) -> str:
        """Get a required environment variable or exit with a clear message."""
        value = os.getenv(name)
        if value is None:
            print(f"Missing required environment variable: {name}", file=sys.stderr)
            sys.exit(1)
        return value

    def _validate_credentials_file(self) -> None:
        """Ensure the Google Drive credentials file exists (file mode only)."""
        creds = self.GOOGLE_DRIVE_CREDENTIALS
        if not isinstance(creds, str):
            return  # JSON mode — no file to validate
        creds_path = Path(creds)
        if not creds_path.is_file():
            print(
                f"Google Drive credentials file not found: {creds_path.resolve()}",
                file=sys.stderr,
            )
            sys.exit(1)


def load_settings() -> Settings:
    """Load and validate all settings. Call once at startup."""
    return Settings()
