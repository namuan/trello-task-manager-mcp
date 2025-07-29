from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, ClassVar


class ServiceConfigError(Exception):
    """Base exception class for service configuration errors."""

    pass


class MissingConfigurationError(ServiceConfigError):
    """Raised when required configuration is missing."""

    def __init__(self, service_name: str, missing_keys: list[str]):
        self.service_name = service_name
        self.missing_keys = missing_keys
        keys_str = ", ".join(missing_keys)
        super().__init__(f"Missing required configuration for {service_name}: {keys_str}")


class InvalidConfigurationError(ServiceConfigError):
    """Raised when configuration values are invalid."""

    def __init__(self, service_name: str, key: str, reason: str):
        self.service_name = service_name
        self.key = key
        self.reason = reason
        super().__init__(f"Invalid configuration for {service_name}.{key}: {reason}")


class ConfigNotFoundError(ServiceConfigError):
    """Raised when a service configuration is not found."""

    def __init__(self, service_name: str):
        self.service_name = service_name
        super().__init__(f"No configuration found for service '{service_name}'")


class UnknownServiceTypeError(ServiceConfigError):
    """Raised when an unknown service type is specified."""

    def __init__(self, service_type: str):
        self.service_type = service_type
        super().__init__(f"Unknown service type: {service_type}")


@dataclass
class ServiceConfig(ABC):
    """Abstract base class for service configurations."""

    service_name: str

    @abstractmethod
    def validate(self) -> None:
        """Validate the configuration.

        Raises:
            MissingConfigurationError: If required configuration is missing
            InvalidConfigurationError: If configuration values are invalid
        """
        pass

    @abstractmethod
    def to_dict(self) -> dict[str, Any]:
        """Convert configuration to dictionary."""
        pass

    @classmethod
    @abstractmethod
    def from_env(cls) -> "ServiceConfig":
        """Create configuration from environment variables."""
        pass

    @classmethod
    @abstractmethod
    def from_dict(cls, config_dict: dict[str, Any]) -> "ServiceConfig":
        """Create configuration from dictionary."""
        pass


@dataclass
class TrelloConfig(ServiceConfig):
    """Configuration for Trello service."""

    api_key: str
    api_token: str
    board_name: str
    service_name: str = "trello"

    def validate(self) -> None:
        """Validate Trello configuration."""
        missing_keys = []

        if not self.api_key:
            missing_keys.append("api_key")
        if not self.api_token:
            missing_keys.append("api_token")
        if not self.board_name:
            missing_keys.append("board_name")

        if missing_keys:
            raise MissingConfigurationError(self.service_name, missing_keys)

        # Validate API key format (basic validation)
        if len(self.api_key) < 10:
            raise InvalidConfigurationError(self.service_name, "api_key", "API key too short")

        # Validate API token format (basic validation)
        if len(self.api_token) < 10:
            raise InvalidConfigurationError(self.service_name, "api_token", "API token too short")

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "service_name": self.service_name,
            "api_key": self.api_key,
            "api_token": self.api_token,
            "board_name": self.board_name,
        }

    @classmethod
    def from_env(cls) -> "TrelloConfig":
        """Create from environment variables."""
        import os

        from dotenv import load_dotenv

        load_dotenv()

        return cls(
            api_key=os.getenv("TRELLO_API_KEY", ""),
            api_token=os.getenv("TRELLO_API_TOKEN", ""),
            board_name=os.getenv("TRELLO_BOARD_NAME", ""),
        )

    @classmethod
    def from_dict(cls, config_dict: dict[str, Any]) -> "TrelloConfig":
        """Create from dictionary."""
        return cls(
            api_key=config_dict.get("api_key", ""),
            api_token=config_dict.get("api_token", ""),
            board_name=config_dict.get("board_name", ""),
        )


@dataclass
class JiraConfig(ServiceConfig):
    """Configuration for JIRA service."""

    server_url: str
    username: str
    api_token: str
    project_key: str
    service_name: str = "jira"

    def validate(self) -> None:
        """Validate JIRA configuration."""
        missing_keys = []

        if not self.server_url:
            missing_keys.append("server_url")
        if not self.username:
            missing_keys.append("username")
        if not self.api_token:
            missing_keys.append("api_token")
        if not self.project_key:
            missing_keys.append("project_key")

        if missing_keys:
            raise MissingConfigurationError(self.service_name, missing_keys)

        # Validate server URL format
        if not (self.server_url.startswith("http://") or self.server_url.startswith("https://")):
            raise InvalidConfigurationError(self.service_name, "server_url", "Must start with http:// or https://")

        # Validate project key format (basic validation)
        if len(self.project_key) < 2:
            raise InvalidConfigurationError(self.service_name, "project_key", "Project key too short")

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "service_name": self.service_name,
            "server_url": self.server_url,
            "username": self.username,
            "api_token": self.api_token,
            "project_key": self.project_key,
        }

    @classmethod
    def from_env(cls) -> "JiraConfig":
        """Create from environment variables."""
        import os

        from dotenv import load_dotenv

        load_dotenv()

        return cls(
            server_url=os.getenv("JIRA_SERVER_URL", ""),
            username=os.getenv("JIRA_USERNAME", ""),
            api_token=os.getenv("JIRA_API_TOKEN", ""),
            project_key=os.getenv("JIRA_PROJECT_KEY", ""),
        )

    @classmethod
    def from_dict(cls, config_dict: dict[str, Any]) -> "JiraConfig":
        """Create from dictionary."""
        return cls(
            server_url=config_dict.get("server_url", ""),
            username=config_dict.get("username", ""),
            api_token=config_dict.get("api_token", ""),
            project_key=config_dict.get("project_key", ""),
        )


class ConfigurationManager:
    """Manages service configurations."""

    _configs: ClassVar[dict[str, ServiceConfig]] = {}

    @classmethod
    def register_config(cls, config: ServiceConfig) -> None:
        """Register a service configuration."""
        config.validate()
        cls._configs[config.service_name] = config

    @classmethod
    def get_config(cls, service_name: str) -> ServiceConfig:
        """Get a service configuration."""
        if service_name not in cls._configs:
            raise ConfigNotFoundError(service_name)
        return cls._configs[service_name]

    @classmethod
    def has_config(cls, service_name: str) -> bool:
        """Check if a service configuration exists."""
        return service_name in cls._configs

    @classmethod
    def list_services(cls) -> list[str]:
        """List all registered service names."""
        return list(cls._configs.keys())

    @classmethod
    def clear_configs(cls) -> None:
        """Clear all configurations (mainly for testing)."""
        cls._configs.clear()

    @classmethod
    def load_from_env(cls, service_type: str) -> ServiceConfig:
        """Load configuration from environment variables."""
        if service_type == "trello":
            config = TrelloConfig.from_env()
        elif service_type == "jira":
            config = JiraConfig.from_env()
        else:
            raise UnknownServiceTypeError(service_type)

        cls.register_config(config)
        return config

    @classmethod
    def get_active_service(cls) -> str | None:
        """Get the active service name from environment or first available."""
        import os

        from dotenv import load_dotenv

        load_dotenv()

        # Check for explicit service selection
        active_service = os.getenv("ACTIVE_TASK_SERVICE")
        if active_service and cls.has_config(active_service):
            return active_service

        # Return first available service
        services = cls.list_services()
        return services[0] if services else None
