"""Shared, sanitized errors and HTTPS-verifying requests to Inji services."""
import time
import requests


class RunnerError(Exception):
    pass


class HandoffFailure(Exception):
    """An observed application outcome incompatible with the test, not an API outage."""


def target_request(method, url, deadline, expected=200, **kwargs):
    for attempt in range(3):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise RunnerError("Inji handoff deadline exceeded")
        try:
            response = requests.request(method, url, timeout=min(30, remaining), verify=True,
                                        allow_redirects=False, **kwargs)
            if response.status_code != expected:
                raise RunnerError(f"Inji handoff returned HTTP {response.status_code}")
            return response.json()
        except requests.exceptions.SSLError as error:
            raise RunnerError("Inji TLS validation failed; configure REQUESTS_CA_BUNDLE") from error
        except (requests.ConnectionError, requests.Timeout) as error:
            if attempt == 2:
                raise RunnerError("Inji connection failed after 3 attempts") from error
            time.sleep(min(2 ** attempt, max(0, deadline - time.monotonic())))
        except (ValueError, requests.RequestException) as error:
            raise RunnerError("Invalid Inji API response") from error
