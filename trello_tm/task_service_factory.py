import inspect
from typing import ClassVar

from .jira_task_service import JiraTaskService
from .service_config import (
    ConfigurationManager,
    InvalidConfigurationError,
    MissingConfigurationError,
    ServiceConfig,
    UnknownServiceTypeError,
)
from .service_types import ServiceType
from .task_service import TaskService, TaskServiceAuthenticationError
from .trello_task_service import TrelloTaskService


class ServiceRegistrationError(Exception):
    """Raised when service registration fails."""

    pass


class ConfigurationValidationError(Exception):
    """Raised when configuration validation fails."""

    pass


class MissingServiceConfigError(Exception):
    """Raised when required service configuration is missing."""

    def __init__(self, service_type: str, missing_keys: list[str] | None = None):
        self.service_type = service_type
        self.missing_keys = missing_keys or []

        if missing_keys:
            keys_str = ", ".join(missing_keys)
            message = f"Missing required configuration for {service_type}: {keys_str}"
        else:
            message = f"Missing configuration for {service_type}"

        super().__init__(message)


class TaskServiceFactory:
    """Factory class for creating task service instances based on configuration."""

    _service_registry: ClassVar[dict[ServiceType, type[TaskService]]] = {}
    _initialized: ClassVar[bool] = False

    @classmethod
    def _initialize_default_services(cls) -> None:
        """Initialize the factory with default services."""
        if not cls._initialized:
            cls._service_registry = {
                ServiceType.TRELLO: TrelloTaskService,
                ServiceType.JIRA: JiraTaskService,
            }
            cls._initialized = True

    @classmethod
    def create_service(cls, service_type: str | ServiceType, config: ServiceConfig | None = None) -> TaskService:
        """Create a task service instance based on the service type.

        Args:
            service_type: The type of service to create ('trello' or 'jira') or ServiceType enum
            config: Optional service configuration. If not provided, will load from environment

        Returns:
            TaskService: An instance of the appropriate task service

        Raises:
            UnknownServiceTypeError: If the service type is not supported
            TaskServiceAuthenticationError: If authentication fails
        """
        cls._initialize_default_services()
        # Convert string to ServiceType if needed
        if isinstance(service_type, str):
            try:
                service_type_enum = ServiceType.from_string(service_type)
            except ValueError as e:
                raise UnknownServiceTypeError(service_type) from e
        else:
            service_type_enum = service_type

        if service_type_enum not in cls._service_registry:
            raise UnknownServiceTypeError(str(service_type_enum))

        # Load and validate configuration
        if config is None:
            try:
                config = ConfigurationManager.load_from_env(str(service_type_enum))
            except MissingConfigurationError as e:
                raise MissingServiceConfigError(str(service_type_enum), e.missing_keys) from e
            except Exception as e:
                raise ConfigurationValidationError(f"Failed to load configuration for {service_type_enum}: {e}") from e
        else:
            # Validate the provided configuration
            cls._validate_configuration(config)
            ConfigurationManager.register_config(config)

        # Get the service class and instantiate it
        service_class = cls._service_registry[service_type_enum]
        try:
            return service_class()
        except Exception as e:
            # Re-raise with more context
            raise TaskServiceAuthenticationError(str(service_type_enum)) from e

    @classmethod
    def create_from_config(cls, config: ServiceConfig) -> TaskService:
        """Create a task service instance from a configuration object.

        Args:
            config: The service configuration

        Returns:
            TaskService: An instance of the appropriate task service

        Raises:
            UnknownServiceTypeError: If the service type is not supported
            TaskServiceAuthenticationError: If authentication fails
        """
        return cls.create_service(config.service_name, config)

    @classmethod
    def create_default_service(cls) -> TaskService:
        """Create a task service instance using the default/active service configuration.

        Returns:
            TaskService: An instance of the default task service

        Raises:
            UnknownServiceTypeError: If no valid service configuration is found
            TaskServiceAuthenticationError: If authentication fails
        """
        cls._initialize_default_services()

        # Try to get active service from environment
        active_service = ConfigurationManager.get_active_service()

        if active_service:
            try:
                return cls.create_service(active_service)
            except (TaskServiceAuthenticationError, UnknownServiceTypeError):
                # If active service fails, fall back to trying others
                pass

        # Try to load services in order of preference
        last_exception = None
        for service_type in [ServiceType.TRELLO, ServiceType.JIRA]:
            try:
                return cls.create_service(service_type)
            except (TaskServiceAuthenticationError, UnknownServiceTypeError) as e:
                last_exception = e
                continue
            except Exception as e:
                last_exception = e
                continue

        # If we get here, no service could be created
        if last_exception:
            raise UnknownServiceTypeError(
                f"No valid service configuration found. Last error: {last_exception}"
            ) from last_exception
        else:
            raise UnknownServiceTypeError("No valid service configuration found")

    @classmethod
    def create_service_with_fallback(
        cls, preferred_service: str | ServiceType, fallback_services: list[str | ServiceType] | None = None
    ) -> TaskService:
        """Create a service with fallback options if the preferred service fails.

        Args:
            preferred_service: The preferred service type to try first
            fallback_services: List of fallback services to try if preferred fails

        Returns:
            TaskService: An instance of a working task service

        Raises:
            UnknownServiceTypeError: If no service could be created
        """
        cls._initialize_default_services()

        if fallback_services is None:
            fallback_services = [ServiceType.TRELLO, ServiceType.JIRA]

        # Try preferred service first
        try:
            return cls.create_service(preferred_service)
        except (TaskServiceAuthenticationError, UnknownServiceTypeError):
            pass

        # Try fallback services
        for fallback_service in fallback_services:
            try:
                return cls.create_service(fallback_service)
            except (TaskServiceAuthenticationError, UnknownServiceTypeError):
                continue

        raise UnknownServiceTypeError(f"Could not create service. Tried: {preferred_service}, {fallback_services}")

    @classmethod
    def create_service_safe(
        cls, service_type: str | ServiceType, config: ServiceConfig | None = None
    ) -> tuple[TaskService | None, str]:
        """Safely create a service instance, returning None and error message on failure.

        Args:
            service_type: The type of service to create
            config: Optional service configuration

        Returns:
            tuple[TaskService | None, str]: Service instance (or None) and status message
        """
        try:
            service = cls.create_service(service_type, config)
            return service, f"Successfully created {service_type} service"
        except UnknownServiceTypeError as e:
            return None, f"Unknown service type: {e}"
        except TaskServiceAuthenticationError as e:
            return None, f"Authentication failed: {e}"
        except MissingServiceConfigError as e:
            return None, f"Missing configuration: {e}"
        except Exception as e:
            return None, f"Failed to create service: {e}"

    @classmethod
    def get_missing_config_help(cls, service_type: str | ServiceType) -> str:
        """Get helpful information about missing configuration for a service.

        Args:
            service_type: The service type to get help for

        Returns:
            str: Helpful message about required configuration
        """
        try:
            service_type_enum = ServiceType.from_string(service_type) if isinstance(service_type, str) else service_type
            service_name = str(service_type_enum)

            if service_name == "trello":
                return (
                    "Trello service requires the following environment variables:\n"
                    "- TRELLO_API_KEY: Your Trello API key\n"
                    "- TRELLO_API_TOKEN: Your Trello API token\n"
                    "- TRELLO_BOARD_NAME: Name of the Trello board to use\n\n"
                    "You can get your API key and token from: https://trello.com/app-key"
                )
            elif service_name == "jira":
                return (
                    "JIRA service requires the following environment variables:\n"
                    "- JIRA_SERVER_URL: Your JIRA server URL (e.g., https://yourcompany.atlassian.net)\n"
                    "- JIRA_USERNAME: Your JIRA username/email\n"
                    "- JIRA_API_TOKEN: Your JIRA API token\n"
                    "- JIRA_PROJECT_KEY: The project key to use\n\n"
                    "You can create an API token at: https://id.atlassian.com/manage-profile/security/api-tokens"
                )
            else:
                return f"Configuration help not available for service type: {service_name}"

        except Exception:
            return "Unable to provide configuration help for unknown service type"

    @classmethod
    def diagnose_configuration_issues(cls) -> dict[str, dict[str, str]]:
        """Diagnose configuration issues for all services.

        Returns:
            dict: Detailed diagnosis for each service type
        """
        diagnosis = {}

        for service_type in ServiceType.get_all_types():
            service_diagnosis = {"status": "unknown", "message": "", "help": ""}

            is_valid, message = cls.validate_service_config(service_type)

            if is_valid:
                service_diagnosis["status"] = "valid"
                service_diagnosis["message"] = message
            else:
                service_diagnosis["status"] = "invalid"
                service_diagnosis["message"] = message
                service_diagnosis["help"] = cls.get_missing_config_help(service_type)

            diagnosis[service_type] = service_diagnosis

        return diagnosis

    @classmethod
    def _validate_configuration(cls, config: ServiceConfig) -> None:
        """Validate a service configuration.

        Args:
            config: The configuration to validate

        Raises:
            ConfigurationValidationError: If the configuration is invalid
        """
        try:
            config.validate()
        except MissingConfigurationError as e:
            raise MissingServiceConfigError(config.service_name, e.missing_keys) from e
        except InvalidConfigurationError as e:
            raise ConfigurationValidationError(f"Invalid configuration for {config.service_name}: {e}") from e
        except Exception as e:
            raise ConfigurationValidationError(f"Unexpected validation error for {config.service_name}: {e}") from e

    @classmethod
    def validate_service_config(cls, service_type: str | ServiceType) -> tuple[bool, str]:
        """Validate configuration for a specific service type.

        Args:
            service_type: The service type to validate configuration for

        Returns:
            tuple[bool, str]: (is_valid, message)
        """
        try:
            # Convert string to ServiceType if needed
            service_type_enum = ServiceType.from_string(service_type) if isinstance(service_type, str) else service_type
            # Try to load configuration from environment
            config = ConfigurationManager.load_from_env(str(service_type_enum))
            cls._validate_configuration(config)
            return True, f"Configuration for {service_type_enum} is valid"
        except MissingServiceConfigError as e:
            return False, f"Missing configuration: {e}"
        except (UnknownServiceTypeError, ConfigurationValidationError) as e:
            return False, str(e)
        except Exception as e:
            return False, f"Unexpected error validating {service_type}: {e}"

    @classmethod
    def validate_all_configs(cls) -> dict[str, tuple[bool, str]]:
        """Validate configurations for all supported service types.

        Returns:
            dict[str, tuple[bool, str]]: Dictionary mapping service names to (is_valid, message)
        """
        results = {}
        for service_type in ServiceType.get_all_types():
            is_valid, message = cls.validate_service_config(service_type)
            results[service_type] = (is_valid, message)
        return results

    @classmethod
    def get_available_services(cls) -> list[str]:
        """Get list of services that have valid configurations.

        Returns:
            list[str]: List of service names with valid configurations
        """
        available = []
        for service_type in ServiceType.get_all_types():
            is_valid, _ = cls.validate_service_config(service_type)
            if is_valid:
                available.append(service_type)
        return available

    @classmethod
    def create_service_with_validation(
        cls, service_type: str | ServiceType, config: ServiceConfig | None = None
    ) -> TaskService:
        """Create a service with explicit configuration validation.

        Args:
            service_type: The type of service to create
            config: Optional service configuration

        Returns:
            TaskService: An instance of the task service

        Raises:
            ConfigurationValidationError: If configuration validation fails
            UnknownServiceTypeError: If the service type is not supported
            TaskServiceAuthenticationError: If authentication fails
        """
        cls._initialize_default_services()

        # Convert string to ServiceType if needed
        if isinstance(service_type, str):
            try:
                service_type_enum = ServiceType.from_string(service_type)
            except ValueError as e:
                raise UnknownServiceTypeError(service_type) from e
        else:
            service_type_enum = service_type

        if service_type_enum not in cls._service_registry:
            raise UnknownServiceTypeError(str(service_type_enum))

        # Load and validate configuration
        if config is None:
            # Validate environment configuration first
            is_valid, message = cls.validate_service_config(service_type_enum)
            if not is_valid:
                if "Missing configuration" in message:
                    # Extract service type for better error message
                    raise MissingServiceConfigError(str(service_type_enum))
                else:
                    raise ConfigurationValidationError(f"Environment configuration invalid: {message}")
            try:
                config = ConfigurationManager.load_from_env(str(service_type_enum))
            except MissingConfigurationError as e:
                raise MissingServiceConfigError(str(service_type_enum), e.missing_keys) from e
        else:
            cls._validate_configuration(config)
            ConfigurationManager.register_config(config)

        # Create the service
        service_class = cls._service_registry[service_type_enum]
        try:
            return service_class()
        except Exception as e:
            raise TaskServiceAuthenticationError(str(service_type_enum)) from e

    @classmethod
    def register_service(cls, service_type: ServiceType, service_class: type[TaskService]) -> None:
        """Register a new service type with the factory.

        Args:
            service_type: The service type enum
            service_class: The service class to register

        Raises:
            ServiceRegistrationError: If the service class is invalid
        """
        cls._validate_service_class(service_class)
        cls._service_registry[service_type] = service_class

    @classmethod
    def register_service_by_name(cls, service_name: str, service_class: type[TaskService]) -> None:
        """Register a service by string name (creates ServiceType if needed).

        Args:
            service_name: The name of the service
            service_class: The service class to register

        Raises:
            ServiceRegistrationError: If the service class is invalid
            ValueError: If the service name is not a valid ServiceType
        """
        try:
            service_type = ServiceType.from_string(service_name)
            cls.register_service(service_type, service_class)
        except ValueError as e:
            raise ServiceRegistrationError(f"Invalid service name '{service_name}': {e}") from e

    @classmethod
    def unregister_service(cls, service_type: ServiceType) -> bool:
        """Unregister a service type from the factory.

        Args:
            service_type: The service type to unregister

        Returns:
            bool: True if the service was unregistered, False if it wasn't registered
        """
        if service_type in cls._service_registry:
            del cls._service_registry[service_type]
            return True
        return False

    @classmethod
    def _validate_service_class(cls, service_class: type[TaskService]) -> None:
        """Validate that a service class is properly implemented.

        Args:
            service_class: The service class to validate

        Raises:
            ServiceRegistrationError: If the service class is invalid
        """
        if not inspect.isclass(service_class):
            raise ServiceRegistrationError("Service must be a class")

        if not issubclass(service_class, TaskService):
            raise ServiceRegistrationError("Service class must inherit from TaskService")

        # Check if all abstract methods are implemented
        abstract_methods = getattr(service_class, "__abstractmethods__", set())
        if abstract_methods:
            raise ServiceRegistrationError(
                f"Service class must implement all abstract methods: {', '.join(abstract_methods)}"
            )

    @classmethod
    def get_registered_services(cls) -> dict[ServiceType, type[TaskService]]:
        """Get a copy of all registered services.

        Returns:
            dict[ServiceType, Type[TaskService]]: Copy of the service registry
        """
        cls._initialize_default_services()
        return cls._service_registry.copy()

    @classmethod
    def clear_registry(cls) -> None:
        """Clear all registered services (mainly for testing)."""
        cls._service_registry.clear()
        cls._initialized = False

    @classmethod
    def get_supported_services(cls) -> list[str]:
        """Get a list of supported service types.

        Returns:
            list[str]: List of supported service type names
        """
        cls._initialize_default_services()
        return [str(service_type) for service_type in cls._service_registry]

    @classmethod
    def is_service_supported(cls, service_type: str | ServiceType) -> bool:
        """Check if a service type is supported.

        Args:
            service_type: The service type to check (string or ServiceType enum)

        Returns:
            bool: True if the service type is supported, False otherwise
        """
        cls._initialize_default_services()
        if isinstance(service_type, str):
            try:
                service_type_enum = ServiceType.from_string(service_type)
                return service_type_enum in cls._service_registry
            except ValueError:
                return False
        else:
            return service_type in cls._service_registry
