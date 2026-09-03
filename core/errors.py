from __future__ import annotations


class SanketError(Exception):
    pass


class ConfigError(SanketError):
    pass


class ProvenanceError(SanketError):
    pass


class TemporalFirewallError(SanketError):
    pass


class RegistryError(SanketError):
    pass


class CorridorError(SanketError):
    pass


class ConnectorError(SanketError):
    pass


class GranuleNotFoundError(ConnectorError):
    pass


class AuthenticationError(ConnectorError):
    pass


class TerrainError(SanketError):
    pass


class NoImpoundmentError(TerrainError):
    pass


class RoutingError(TerrainError):
    pass


class DetectionError(SanketError):
    pass


class BaselineNotEstimableError(DetectionError):
    pass


class RouterError(SanketError):
    pass


class AllProvidersFailedError(RouterError):
    pass


class BudgetExceededError(RouterError):
    pass


class LedgerError(SanketError):
    pass


class ClaimNotInLedgerError(LedgerError):
    pass


class StepLimitReachedError(LedgerError):
    pass


class VerificationError(SanketError):
    pass


class VetoedError(VerificationError):
    pass


class GateError(SanketError):
    pass


class GateNotApprovedError(GateError):
    pass


class UnauthorisedApproverError(GateError):
    pass


class CooldownActiveError(GateError):
    pass


class NotOptedInError(GateError):
    pass


class ChannelError(SanketError):
    pass


class DeliveryFailedError(ChannelError):
    pass


class SandboxError(SanketError):
    pass


class SandboxTimeoutError(SandboxError):
    pass


class SandboxWriteAttemptError(SandboxError):
    pass
