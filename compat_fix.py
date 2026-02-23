"""
Compatibility fix for Python 3.9 with importlib.metadata.packages_distributions
This must be imported BEFORE any packages that use this function (like elevenlabs, google-generativeai)
"""
import sys

if sys.version_info < (3, 10):
    try:
        import importlib.metadata
        # Check if packages_distributions exists, if not, add a fallback
        if not hasattr(importlib.metadata, 'packages_distributions'):
            # packages_distributions() returns a dict mapping package names to distribution names
            def _packages_distributions():
                """Fallback implementation for packages_distributions (Python 3.9 compatibility)"""
                try:
                    distributions = {}
                    for dist in importlib.metadata.distributions():
                        try:
                            name = dist.metadata.get('Name') or dist.metadata.get('name')
                            if name:
                                normalized_name = name.lower().replace('-', '_').replace('.', '_')
                                if normalized_name not in distributions:
                                    distributions[normalized_name] = []
                                distributions[normalized_name].append(name)
                        except:
                            pass
                    return distributions
                except:
                    return {}
            # Add the function to importlib.metadata module
            importlib.metadata.packages_distributions = _packages_distributions
    except Exception:
        # Silently fail - if we can't patch it, imports will fail later
        pass

