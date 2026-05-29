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
        self.XAI_MODEL: str = os.getenv("XAI_MODEL", "grok-2-vision-1212")

        # Google Drive
        self.GOOGLE_DRIVE_CREDENTIALS: str = self._require("GOOGLE_DRIVE_CREDENTIALS")
        self.GOOGLE_DRIVE_FOLDER_ID: str = self._require("GOOGLE_DRIVE_FOLDER_ID")
        self.GOOGLE_DRIVE_INBOX_FOLDER_ID: str = os.getenv(
            "GOOGLE_DRIVE_INBOX_FOLDER_ID", ""
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

        # Email (IMAP) — optional, for email channel
        self.EMAIL_IMAP_HOST: str = os.getenv("EMAIL_IMAP_HOST", "")
        self.EMAIL_IMAP_PORT: int = int(os.getenv("EMAIL_IMAP_PORT", "993"))
        self.EMAIL_IMAP_USERNAME: str = os.getenv("EMAIL_IMAP_USERNAME", "")
        self.EMAIL_IMAP_PASSWORD: str = os.getenv("EMAIL_IMAP_PASSWORD", "")
        self.EMAIL_POLL_INTERVAL_S: int = int(os.getenv("EMAIL_POLL_INTERVAL_S", "60"))

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
        """Ensure the Google Drive credentials file exists."""
        creds_path = Path(self.GOOGLE_DRIVE_CREDENTIALS)
        if not creds_path.is_file():
            print(
                f"Google Drive credentials file not found: {creds_path.resolve()}",
                file=sys.stderr,
            )
            sys.exit(1)


def load_settings() -> Settings:
    """Load and validate all settings. Call once at startup."""
    return Settings()
