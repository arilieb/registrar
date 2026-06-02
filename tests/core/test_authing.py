# -*- encoding: utf-8 -*-
"""
Unit tests for registrar.core.authing module
"""

import pytest
from unittest.mock import Mock
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response

from registrar.core.authing import SignatureValidationComponent


class TestSignatureValidationComponent:
    """Test suite for SignatureValidationComponent path matching"""

    @pytest.fixture
    def mock_authn(self):
        """Create a mock Authenticater instance"""
        authn = Mock()
        # By default, verification fails (returns False)
        # This simulates missing or invalid authentication
        authn.verify = Mock(return_value=False)
        authn.resource = Mock(return_value="test-resource")
        authn.sign = Mock(return_value={})
        authn.hab = Mock()
        authn.hab.pre = "test-pre"
        return authn

    @pytest.fixture
    def mock_app(self):
        """Create a mock Starlette app instance"""
        return Starlette()

    @pytest.fixture
    def mock_request(self):
        """Create a mock request"""
        request = Mock(spec=Request)
        request.url = Mock()
        request.state = Mock()
        request.method = "GET"
        request.headers = {}
        return request

    @pytest.fixture
    def mock_call_next(self):
        """Create a mock call_next function"""

        async def call_next(request):
            response = Response(content=b"test response", status_code=200)

            # Add body_iterator for middleware to consume
            async def body_iterator():
                yield b"test response"

            response.body_iterator = body_iterator()
            return response

        return call_next

    @pytest.mark.asyncio
    async def test_exact_match_root_only(
        self, mock_app, mock_authn, mock_request, mock_call_next
    ):
        """Test that "/" pattern matches only root path, not all paths"""
        middleware = SignatureValidationComponent(mock_app, mock_authn, allowed=["/"])

        # Test root path - should match and allow
        mock_request.url.path = "/"
        response = await middleware.dispatch(mock_request, mock_call_next)
        assert response.status_code == 200
        mock_authn.verify.assert_not_called()  # Should skip auth

        # Test non-root path - should NOT match and require auth
        mock_authn.verify.reset_mock()
        mock_request.url.path = "/foo"
        response = await middleware.dispatch(mock_request, mock_call_next)
        # Without proper auth headers, should return 401
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_parameterized_path_matching(
        self, mock_app, mock_authn, mock_request, mock_call_next
    ):
        """Test parameterized paths like /registry/{regi}"""
        middleware = SignatureValidationComponent(
            mock_app, mock_authn, allowed=["/registry/{regi}"]
        )

        # Should match /registry/abc
        mock_request.url.path = "/registry/abc"
        response = await middleware.dispatch(mock_request, mock_call_next)
        assert response.status_code == 200

        # Should match /registry/123
        mock_request.url.path = "/registry/123"
        response = await middleware.dispatch(mock_request, mock_call_next)
        assert response.status_code == 200

        # Should NOT match /registry/ (missing parameter)
        mock_request.url.path = "/registry/"
        response = await middleware.dispatch(mock_request, mock_call_next)
        assert response.status_code == 401

        # Should NOT match /registry/a/b (extra path segment)
        mock_request.url.path = "/registry/a/b"
        response = await middleware.dispatch(mock_request, mock_call_next)
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_wildcard_path_matching(
        self, mock_app, mock_authn, mock_request, mock_call_next
    ):
        """Test wildcard paths like /public/{path:path}"""
        middleware = SignatureValidationComponent(
            mock_app, mock_authn, allowed=["/public/{path:path}"]
        )

        # Should match /public/foo
        mock_request.url.path = "/public/foo"
        response = await middleware.dispatch(mock_request, mock_call_next)
        assert response.status_code == 200

        # Should match /public/foo/bar/baz (multiple segments)
        mock_request.url.path = "/public/foo/bar/baz"
        response = await middleware.dispatch(mock_request, mock_call_next)
        assert response.status_code == 200

        # Should match /public/ (empty path segment - {path:path} uses .* which matches empty)
        mock_request.url.path = "/public/"
        response = await middleware.dispatch(mock_request, mock_call_next)
        assert response.status_code == 200

        # Should NOT match /public (no trailing slash)
        mock_request.url.path = "/public"
        response = await middleware.dispatch(mock_request, mock_call_next)
        assert response.status_code == 401

        # Should NOT match /private/foo
        mock_request.url.path = "/private/foo"
        response = await middleware.dispatch(mock_request, mock_call_next)
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_multiple_patterns(
        self, mock_app, mock_authn, mock_request, mock_call_next
    ):
        """Test multiple allowed patterns work correctly"""
        middleware = SignatureValidationComponent(
            mock_app, mock_authn, allowed=["/", "/health", "/api/{id}"]
        )

        # Test root
        mock_request.url.path = "/"
        response = await middleware.dispatch(mock_request, mock_call_next)
        assert response.status_code == 200

        # Test /health
        mock_request.url.path = "/health"
        response = await middleware.dispatch(mock_request, mock_call_next)
        assert response.status_code == 200

        # Test /api/123
        mock_request.url.path = "/api/123"
        response = await middleware.dispatch(mock_request, mock_call_next)
        assert response.status_code == 200

        # Test unmatched path
        mock_request.url.path = "/protected"
        response = await middleware.dispatch(mock_request, mock_call_next)
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_pattern_priority_first_match_wins(
        self, mock_app, mock_authn, mock_request, mock_call_next
    ):
        """Test that first matching pattern is used"""
        middleware = SignatureValidationComponent(
            mock_app, mock_authn, allowed=["/api/{id}", "/api/special"]
        )

        # Both patterns could match /api/special, but first one should win
        mock_request.url.path = "/api/special"
        response = await middleware.dispatch(mock_request, mock_call_next)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_invalid_pattern_logs_warning(self, mock_app, mock_authn, caplog):
        """Test that invalid patterns log warnings but don't crash"""
        # Create middleware with an invalid pattern (this would cause compile error)
        # Starlette's compile_path should handle most patterns, but we can test error handling
        import logging

        with caplog.at_level(logging.WARNING):
            middleware = SignatureValidationComponent(
                mock_app, mock_authn, allowed=["/valid", "invalid-pattern-{"]
            )

        # Check that valid patterns still work
        assert len(middleware.allowed_patterns) >= 1

    @pytest.mark.asyncio
    async def test_empty_allowed_list(
        self, mock_app, mock_authn, mock_request, mock_call_next
    ):
        """Test that empty allowed list requires auth for all paths"""
        middleware = SignatureValidationComponent(mock_app, mock_authn, allowed=[])

        # All paths should require authentication
        mock_request.url.path = "/"
        response = await middleware.dispatch(mock_request, mock_call_next)
        assert response.status_code == 401

        mock_request.url.path = "/any/path"
        response = await middleware.dispatch(mock_request, mock_call_next)
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_no_false_prefix_matches(
        self, mock_app, mock_authn, mock_request, mock_call_next
    ):
        """Test that /tel doesn't match /telephone (prefix matching issue)"""
        middleware = SignatureValidationComponent(
            mock_app, mock_authn, allowed=["/tel"]
        )

        # Should match /tel exactly
        mock_request.url.path = "/tel"
        response = await middleware.dispatch(mock_request, mock_call_next)
        assert response.status_code == 200

        # Should NOT match /telephone
        mock_request.url.path = "/telephone"
        response = await middleware.dispatch(mock_request, mock_call_next)
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_exact_path_matching(
        self, mock_app, mock_authn, mock_request, mock_call_next
    ):
        """Test exact path matching for simple paths"""
        middleware = SignatureValidationComponent(
            mock_app, mock_authn, allowed=["/health"]
        )

        # Should match /health exactly
        mock_request.url.path = "/health"
        response = await middleware.dispatch(mock_request, mock_call_next)
        assert response.status_code == 200

        # Should NOT match /health/check
        mock_request.url.path = "/health/check"
        response = await middleware.dispatch(mock_request, mock_call_next)
        assert response.status_code == 401

        # Should NOT match /healthz
        mock_request.url.path = "/healthz"
        response = await middleware.dispatch(mock_request, mock_call_next)
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_integer_parameter_pattern(
        self, mock_app, mock_authn, mock_request, mock_call_next
    ):
        """Test integer parameter pattern /api/v{version:int}"""
        middleware = SignatureValidationComponent(
            mock_app, mock_authn, allowed=["/api/v{version:int}"]
        )

        # Should match /api/v1
        mock_request.url.path = "/api/v1"
        response = await middleware.dispatch(mock_request, mock_call_next)
        assert response.status_code == 200

        # Should match /api/v2
        mock_request.url.path = "/api/v2"
        response = await middleware.dispatch(mock_request, mock_call_next)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_none_allowed_defaults_to_empty_list(
        self, mock_app, mock_authn, mock_request, mock_call_next
    ):
        """Test that None for allowed defaults to empty list"""
        middleware = SignatureValidationComponent(mock_app, mock_authn, allowed=None)

        # Should require auth for all paths
        mock_request.url.path = "/"
        response = await middleware.dispatch(mock_request, mock_call_next)
        assert response.status_code == 401
