from enum import Enum


class ServiceType(Enum):
    """Enumeration of supported task service types."""

    TRELLO = "trello"
    JIRA = "jira"

    @classmethod
    def from_string(cls, service_type: str) -> "ServiceType":
        """Create ServiceType from string value.

        Args:
            service_type: String representation of the service type

        Returns:
            ServiceType: The corresponding enum value

        Raises:
            ValueError: If the service type is not supported
        """
        try:
            return cls(service_type.lower())
        except ValueError:
            supported_types = [t.value for t in cls]
            raise ValueError(f"Unsupported service type '{service_type}'. Supported types: {supported_types}") from None

    @classmethod
    def get_all_types(cls) -> list[str]:
        """Get all supported service type strings.

        Returns:
            list[str]: List of all supported service type strings
        """
        return [service_type.value for service_type in cls]

    def __str__(self) -> str:
        """String representation of the service type."""
        return self.value
