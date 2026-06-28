try:
    from .spotify_integration import SpotifyIntegration
except ImportError:
    SpotifyIntegration = None  # type: ignore[assignment,misc]

try:
    from .github_integration import GitHubIntegration
except ImportError:
    GitHubIntegration = None  # type: ignore[assignment,misc]

try:
    from .google_integration import GoogleIntegration
except ImportError:
    GoogleIntegration = None  # type: ignore[assignment,misc]

try:
    from .vscode_context import VSCodeContext
except ImportError:
    VSCodeContext = None  # type: ignore[assignment,misc]

__all__ = ["SpotifyIntegration", "GitHubIntegration", "GoogleIntegration", "VSCodeContext"]
