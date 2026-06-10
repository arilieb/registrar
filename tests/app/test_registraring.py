# -*- encoding: utf-8 -*-
"""
Unit tests for registrar.app.registraring module
"""

import pytest
from unittest.mock import Mock, patch, ANY
from pathlib import Path

from registrar.app.registraring import setup_local


class TestSetupLocal:
    """Test suite for setup_local function"""

    @pytest.fixture
    def mock_habery(self):
        """Create a mock Habery instance"""
        habery = Mock()
        habery.name = "test-name"
        return habery

    @pytest.fixture
    def mock_regery(self):
        """Create a mock Regery instance"""
        return Mock()

    @pytest.fixture
    def mock_hab(self):
        """Create a mock habitat/identifier"""
        hab = Mock()
        hab.name = "test-alias"
        return hab

    @pytest.fixture
    def setup_params(self, tmp_path):
        """Common setup parameters for tests"""
        return {
            "name": "test-db",
            "alias": "test-alias",
            "base": "/tmp/keri",
            "bran": "0123456789abcdefghijkl",
            "issuer": "EBfdLv2XaD_HaABMmPWRVMdKWSm7xvlbemcRMT-KQOQQ",
            "schema": "EBfdLv2XaD_HaABMmPWRVMdKWSm7xvlbemcRMT-SCHEMA",
            "export_dir": tmp_path / "exports",
        }

    @pytest.mark.asyncio
    @patch("registrar.app.registraring.Oobiery")
    @patch("registrar.app.registraring.habbing.Habery")
    @patch("registrar.app.registraring.credentialing.Regery")
    @patch("registrar.app.registraring.RegistrarAPIService")
    @patch("registrar.app.registraring.SentinelConfig")
    @patch("registrar.app.registraring.RegistrarEventHandler")
    @patch("registrar.app.registraring.register_handler")
    @patch("registrar.app.registraring.AppBaser")
    @patch("registrar.app.registraring.FileWatchingService")
    async def test_setup_local_with_existing_hab(
        self,
        mock_file_watching_service,
        mock_app_baser,
        mock_register_handler,
        mock_event_handler,
        mock_sentinel_config,
        mock_api_service,
        mock_regery_class,
        mock_habery_class,
        mock_oobiery_class,
        setup_params,
        mock_habery,
        mock_regery,
        mock_hab,
    ):
        """Test setup_local when hab already exists"""
        # Setup mocks
        mock_habery_class.return_value = mock_habery
        mock_regery_class.return_value = mock_regery
        mock_habery.habByName.return_value = mock_hab

        # Mock hab.endsFor to return HTTP endpoint
        mock_hab.pre = "EBfdLv2XaD_HaABMmPWRVMdKWSm7xvlbemcRMT-HABPRE"
        mock_hab.endsFor.return_value = {
            "controller": {mock_hab.pre: {"http": "http://127.0.0.1:8080"}}
        }

        # Mock service instances
        mock_api_instance = Mock()
        mock_api_service.return_value = mock_api_instance
        mock_file_watching_instance = Mock()
        mock_file_watching_service.return_value = mock_file_watching_instance
        mock_config_instance = Mock()
        mock_sentinel_config.return_value = mock_config_instance
        mock_handler_instance = Mock()
        mock_event_handler.return_value = mock_handler_instance
        mock_sentinel_db_instance = Mock()
        mock_app_baser.return_value = mock_sentinel_db_instance
        mock_oobiery_instance = Mock()
        mock_oobiery_class.return_value = mock_oobiery_instance

        # Execute
        services = await setup_local(**setup_params)

        # Verify Habery initialization
        mock_habery_class.assert_called_once_with(
            name="test-db", base="/tmp/keri", bran="0123456789abcdefghijkl"
        )

        # Verify Regery initialization
        mock_regery_class.assert_called_once_with(
            hby=mock_habery, name="test-db", base="/tmp/keri"
        )

        # Verify hab lookup
        mock_habery.habByName.assert_called_once_with("test-alias")

        # Verify makeHab was NOT called since hab exists
        mock_habery.makeHab.assert_not_called()

        # Verify API service creation with new signature
        mock_api_service.assert_called_once_with(
            hby=mock_habery,
            hab=mock_hab,
            org=ANY,
            issuer=setup_params["issuer"],
            rgy=mock_regery,
            host="127.0.0.1",
            port=8080,
            schema=setup_params["schema"],
        )

        # Verify SentinelConfig creation
        mock_sentinel_config.assert_called_once_with(
            hby=mock_habery,
            export_dir=str(setup_params["export_dir"]),
            poll_interval=3.0,
        )

        # Verify RegistrarEventHandler creation and registration
        mock_event_handler.assert_called_once_with(mock_config_instance)
        mock_register_handler.assert_called_once_with(mock_handler_instance)

        # Verify AppBaser creation
        mock_app_baser.assert_called_once_with(
            name=mock_habery.name, headDirPath=setup_params["export_dir"]
        )

        # Verify FileWatchingService creation
        mock_file_watching_service.assert_called_once_with(
            export_dir=setup_params["export_dir"],
            poll_interval=3.0,
            hby=mock_habery,
            rgy=mock_regery,
            db=mock_sentinel_db_instance,
        )

        # Verify services list
        assert len(services) == 3
        assert mock_api_instance in services
        assert mock_file_watching_instance in services
        assert mock_oobiery_instance in services

    @pytest.mark.asyncio
    @patch("registrar.app.registraring.Oobiery")
    @patch("registrar.app.registraring.habbing.Habery")
    @patch("registrar.app.registraring.credentialing.Regery")
    @patch("registrar.app.registraring.RegistrarAPIService")
    @patch("registrar.app.registraring.SentinelConfig")
    @patch("registrar.app.registraring.RegistrarEventHandler")
    @patch("registrar.app.registraring.register_handler")
    @patch("registrar.app.registraring.AppBaser")
    @patch("registrar.app.registraring.FileWatchingService")
    async def test_setup_local_without_existing_hab(
        self,
        mock_file_watching_service,
        mock_app_baser,
        mock_register_handler,
        mock_event_handler,
        mock_sentinel_config,
        mock_api_service,
        mock_regery_class,
        mock_habery_class,
        mock_oobiery_class,
        setup_params,
        mock_habery,
        mock_regery,
        mock_hab,
    ):
        """Test setup_local when hab doesn't exist and needs to be created"""
        # Setup mocks
        mock_habery_class.return_value = mock_habery
        mock_regery_class.return_value = mock_regery
        mock_habery.habByName.return_value = None  # Hab doesn't exist
        mock_habery.makeHab.return_value = mock_hab

        # Mock hab.endsFor to return HTTP endpoint
        mock_hab.pre = "EBfdLv2XaD_HaABMmPWRVMdKWSm7xvlbemcRMT-HABPRE"
        mock_hab.endsFor.return_value = {
            "controller": {mock_hab.pre: {"http": "http://127.0.0.1:8080"}}
        }

        # Mock service instances
        mock_api_instance = Mock()
        mock_api_service.return_value = mock_api_instance
        mock_file_watching_instance = Mock()
        mock_file_watching_service.return_value = mock_file_watching_instance

        # Execute
        services = await setup_local(**setup_params)

        # Verify hab lookup
        mock_habery.habByName.assert_called_once_with("test-alias")

        # Verify makeHab was called since hab doesn't exist
        mock_habery.makeHab.assert_called_once_with(
            name="test-alias", transferable=False
        )

        # Verify services are still created
        assert len(services) == 3

    @pytest.mark.asyncio
    @patch("registrar.app.registraring.habbing.Habery")
    @patch("registrar.app.registraring.credentialing.Regery")
    @patch("registrar.app.registraring.RegistrarAPIService")
    @patch("registrar.app.registraring.SentinelConfig")
    @patch("registrar.app.registraring.RegistrarEventHandler")
    @patch("registrar.app.registraring.register_handler")
    @patch("registrar.app.registraring.AppBaser")
    @patch("registrar.app.registraring.FileWatchingService")
    async def test_setup_local_with_custom_http_port(
        self,
        mock_file_watching_service,
        mock_app_baser,
        mock_register_handler,
        mock_event_handler,
        mock_sentinel_config,
        mock_api_service,
        mock_regery_class,
        mock_habery_class,
        setup_params,
        mock_habery,
        mock_regery,
        mock_hab,
    ):
        """Test setup_local with custom HTTP port from hab endpoint"""
        # Setup mocks
        mock_habery_class.return_value = mock_habery
        mock_regery_class.return_value = mock_regery
        mock_habery.habByName.return_value = mock_hab
        mock_api_instance = Mock()
        mock_api_service.return_value = mock_api_instance

        # Mock hab.endsFor to return HTTP endpoint with custom port
        mock_hab.pre = "EBfdLv2XaD_HaABMmPWRVMdKWSm7xvlbemcRMT-HABPRE"
        mock_hab.endsFor.return_value = {
            "controller": {mock_hab.pre: {"http": "http://127.0.0.1:9090"}}
        }

        # Execute
        await setup_local(**setup_params)

        # Verify API service created with custom port from endpoint
        mock_api_service.assert_called_once_with(
            hby=mock_habery,
            hab=mock_hab,
            org=ANY,
            issuer=setup_params["issuer"],
            rgy=mock_regery,
            host="127.0.0.1",
            port=9090,
            schema=setup_params["schema"],
        )

    @pytest.mark.asyncio
    @patch("registrar.app.registraring.habbing.Habery")
    @patch("registrar.app.registraring.credentialing.Regery")
    @patch("registrar.app.registraring.RegistrarAPIService")
    @patch("registrar.app.registraring.SentinelConfig")
    @patch("registrar.app.registraring.RegistrarEventHandler")
    @patch("registrar.app.registraring.register_handler")
    @patch("registrar.app.registraring.AppBaser")
    @patch("registrar.app.registraring.FileWatchingService")
    async def test_setup_local_default_http_port(
        self,
        mock_file_watching_service,
        mock_app_baser,
        mock_register_handler,
        mock_event_handler,
        mock_sentinel_config,
        mock_api_service,
        mock_regery_class,
        mock_habery_class,
        setup_params,
        mock_habery,
        mock_regery,
        mock_hab,
    ):
        """Test setup_local with default HTTP port when not specified in endpoint"""
        # Setup mocks
        mock_habery_class.return_value = mock_habery
        mock_regery_class.return_value = mock_regery
        mock_habery.habByName.return_value = mock_hab
        mock_api_instance = Mock()
        mock_api_service.return_value = mock_api_instance

        # Mock hab.endsFor to return HTTP endpoint without port (defaults to 80)
        mock_hab.pre = "EBfdLv2XaD_HaABMmPWRVMdKWSm7xvlbemcRMT-HABPRE"
        mock_hab.endsFor.return_value = {
            "controller": {mock_hab.pre: {"http": "http://127.0.0.1"}}
        }

        # Execute
        await setup_local(**setup_params)

        # Verify API service created with default port 80
        mock_api_service.assert_called_once_with(
            hby=mock_habery,
            hab=mock_hab,
            org=ANY,
            issuer=setup_params["issuer"],
            rgy=mock_regery,
            host="127.0.0.1",
            port=80,
            schema=setup_params["schema"],
        )

    @pytest.mark.asyncio
    @patch("registrar.app.registraring.habbing.Habery")
    @patch("registrar.app.registraring.credentialing.Regery")
    @patch("registrar.app.registraring.RegistrarAPIService")
    @patch("registrar.app.registraring.SentinelConfig")
    @patch("registrar.app.registraring.RegistrarEventHandler")
    @patch("registrar.app.registraring.register_handler")
    @patch("registrar.app.registraring.AppBaser")
    @patch("registrar.app.registraring.FileWatchingService")
    async def test_setup_local_poll_interval_configuration(
        self,
        mock_file_watching_service,
        mock_app_baser,
        mock_register_handler,
        mock_event_handler,
        mock_sentinel_config,
        mock_api_service,
        mock_regery_class,
        mock_habery_class,
        setup_params,
        mock_habery,
        mock_regery,
        mock_hab,
    ):
        """Test that poll_interval is correctly configured in both SentinelConfig and FileWatchingService"""
        # Setup mocks
        mock_habery_class.return_value = mock_habery
        mock_regery_class.return_value = mock_regery
        mock_habery.habByName.return_value = mock_hab

        # Mock hab.endsFor to return HTTP endpoint
        mock_hab.pre = "EBfdLv2XaD_HaABMmPWRVMdKWSm7xvlbemcRMT-HABPRE"
        mock_hab.endsFor.return_value = {
            "controller": {mock_hab.pre: {"http": "http://127.0.0.1:8080"}}
        }

        # Execute
        await setup_local(**setup_params)

        # Verify poll_interval is 3.0 in both places
        mock_sentinel_config.assert_called_once()
        sentinel_config_call = mock_sentinel_config.call_args
        assert sentinel_config_call.kwargs["poll_interval"] == 3.0

        mock_file_watching_service.assert_called_once()
        file_watching_call = mock_file_watching_service.call_args
        assert file_watching_call.kwargs["poll_interval"] == 3.0

    @pytest.mark.asyncio
    @patch("registrar.app.registraring.habbing.Habery")
    @patch("registrar.app.registraring.credentialing.Regery")
    @patch("registrar.app.registraring.RegistrarAPIService")
    @patch("registrar.app.registraring.SentinelConfig")
    @patch("registrar.app.registraring.RegistrarEventHandler")
    @patch("registrar.app.registraring.register_handler")
    @patch("registrar.app.registraring.AppBaser")
    @patch("registrar.app.registraring.FileWatchingService")
    async def test_setup_local_export_dir_string_conversion(
        self,
        mock_file_watching_service,
        mock_app_baser,
        mock_register_handler,
        mock_event_handler,
        mock_sentinel_config,
        mock_api_service,
        mock_regery_class,
        mock_habery_class,
        setup_params,
        mock_habery,
        mock_regery,
        mock_hab,
    ):
        """Test that export_dir is converted to string for SentinelConfig but kept as-is for other services"""
        # Setup mocks
        mock_habery_class.return_value = mock_habery
        mock_regery_class.return_value = mock_regery
        mock_habery.habByName.return_value = mock_hab

        # Mock hab.endsFor to return HTTP endpoint
        mock_hab.pre = "EBfdLv2XaD_HaABMmPWRVMdKWSm7xvlbemcRMT-HABPRE"
        mock_hab.endsFor.return_value = {
            "controller": {mock_hab.pre: {"http": "http://127.0.0.1:8080"}}
        }

        export_dir = Path("/tmp/test/exports")
        setup_params["export_dir"] = export_dir

        # Execute
        await setup_local(**setup_params)

        # Verify SentinelConfig gets string version
        sentinel_config_call = mock_sentinel_config.call_args
        assert sentinel_config_call.kwargs["export_dir"] == str(export_dir)

        # Verify FileWatchingService gets the original object
        file_watching_call = mock_file_watching_service.call_args
        assert file_watching_call.kwargs["export_dir"] == export_dir

        # Verify AppBaser gets the original object
        app_baser_call = mock_app_baser.call_args
        assert app_baser_call.kwargs["headDirPath"] == export_dir

    @pytest.mark.asyncio
    @patch("registrar.app.registraring.Oobiery")
    @patch("registrar.app.registraring.habbing.Habery")
    @patch("registrar.app.registraring.credentialing.Regery")
    @patch("registrar.app.registraring.RegistrarAPIService")
    @patch("registrar.app.registraring.SentinelConfig")
    @patch("registrar.app.registraring.RegistrarEventHandler")
    @patch("registrar.app.registraring.register_handler")
    @patch("registrar.app.registraring.AppBaser")
    @patch("registrar.app.registraring.FileWatchingService")
    async def test_setup_local_db_is_none(
        self,
        mock_file_watching_service,
        mock_app_baser,
        mock_register_handler,
        mock_event_handler,
        mock_sentinel_config,
        mock_api_service,
        mock_regery_class,
        mock_habery_class,
        mock_oobiery_class,
        setup_params,
        mock_habery,
        mock_regery,
        mock_hab,
    ):
        """Test that IPEXSocketListener is not added when db is None"""
        # Setup mocks
        mock_habery_class.return_value = mock_habery
        mock_regery_class.return_value = mock_regery
        mock_habery.habByName.return_value = mock_hab

        # Mock hab.endsFor to return HTTP endpoint
        mock_hab.pre = "EBfdLv2XaD_HaABMmPWRVMdKWSm7xvlbemcRMT-HABPRE"
        mock_hab.endsFor.return_value = {
            "controller": {mock_hab.pre: {"http": "http://127.0.0.1:8080"}}
        }

        # Execute
        services = await setup_local(**setup_params)

        # Verify API service, FileWatchingService, and Oobiery are in the list
        assert len(services) == 3

    @pytest.mark.asyncio
    @patch("registrar.app.registraring.Oobiery")
    @patch("registrar.app.registraring.habbing.Habery")
    @patch("registrar.app.registraring.credentialing.Regery")
    @patch("registrar.app.registraring.RegistrarAPIService")
    @patch("registrar.app.registraring.SentinelConfig")
    @patch("registrar.app.registraring.RegistrarEventHandler")
    @patch("registrar.app.registraring.register_handler")
    @patch("registrar.app.registraring.AppBaser")
    @patch("registrar.app.registraring.FileWatchingService")
    async def test_setup_local_services_order(
        self,
        mock_file_watching_service,
        mock_app_baser,
        mock_register_handler,
        mock_event_handler,
        mock_sentinel_config,
        mock_api_service,
        mock_regery_class,
        mock_habery_class,
        mock_oobiery_class,
        setup_params,
        mock_habery,
        mock_regery,
        mock_hab,
    ):
        """Test that services are returned in the correct order"""
        # Setup mocks
        mock_habery_class.return_value = mock_habery
        mock_regery_class.return_value = mock_regery
        mock_habery.habByName.return_value = mock_hab

        # Mock hab.endsFor to return HTTP endpoint
        mock_hab.pre = "EBfdLv2XaD_HaABMmPWRVMdKWSm7xvlbemcRMT-HABPRE"
        mock_hab.endsFor.return_value = {
            "controller": {mock_hab.pre: {"http": "http://127.0.0.1:8080"}}
        }

        mock_api_instance = Mock()
        mock_api_service.return_value = mock_api_instance
        mock_file_watching_instance = Mock()
        mock_file_watching_service.return_value = mock_file_watching_instance
        mock_oobiery_instance = Mock()
        mock_oobiery_class.return_value = mock_oobiery_instance

        # Execute
        services = await setup_local(**setup_params)

        # Verify order: API service, then FileWatchingService, then Oobiery
        assert services[0] == mock_api_instance
        assert services[1] == mock_file_watching_instance
        assert services[2] == mock_oobiery_instance

    @pytest.mark.asyncio
    @patch("registrar.app.registraring.habbing.Habery")
    @patch("registrar.app.registraring.credentialing.Regery")
    @patch("registrar.app.registraring.RegistrarAPIService")
    @patch("registrar.app.registraring.SentinelConfig")
    @patch("registrar.app.registraring.RegistrarEventHandler")
    @patch("registrar.app.registraring.register_handler")
    @patch("registrar.app.registraring.AppBaser")
    @patch("registrar.app.registraring.FileWatchingService")
    async def test_setup_local_handler_registration(
        self,
        mock_file_watching_service,
        mock_app_baser,
        mock_register_handler,
        mock_event_handler,
        mock_sentinel_config,
        mock_api_service,
        mock_regery_class,
        mock_habery_class,
        setup_params,
        mock_habery,
        mock_regery,
        mock_hab,
    ):
        """Test that event handler is created and registered correctly"""
        # Setup mocks
        mock_habery_class.return_value = mock_habery
        mock_regery_class.return_value = mock_regery
        mock_habery.habByName.return_value = mock_hab

        # Mock hab.endsFor to return HTTP endpoint
        mock_hab.pre = "EBfdLv2XaD_HaABMmPWRVMdKWSm7xvlbemcRMT-HABPRE"
        mock_hab.endsFor.return_value = {
            "controller": {mock_hab.pre: {"http": "http://127.0.0.1:8080"}}
        }

        mock_config_instance = Mock()
        mock_sentinel_config.return_value = mock_config_instance
        mock_handler_instance = Mock()
        mock_event_handler.return_value = mock_handler_instance

        # Execute
        await setup_local(**setup_params)

        # Verify handler creation with config
        mock_event_handler.assert_called_once_with(mock_config_instance)

        # Verify handler registration
        mock_register_handler.assert_called_once_with(mock_handler_instance)

    @pytest.mark.asyncio
    @patch("registrar.app.registraring.habbing.Habery")
    @patch("registrar.app.registraring.credentialing.Regery")
    @patch("registrar.app.registraring.RegistrarAPIService")
    @patch("registrar.app.registraring.SentinelConfig")
    @patch("registrar.app.registraring.RegistrarEventHandler")
    @patch("registrar.app.registraring.register_handler")
    @patch("registrar.app.registraring.AppBaser")
    @patch("registrar.app.registraring.FileWatchingService")
    async def test_setup_local_sentinel_db_creation(
        self,
        mock_file_watching_service,
        mock_app_baser,
        mock_register_handler,
        mock_event_handler,
        mock_sentinel_config,
        mock_api_service,
        mock_regery_class,
        mock_habery_class,
        setup_params,
        mock_habery,
        mock_regery,
        mock_hab,
    ):
        """Test that AppBaser (sentinel_db) is created with correct parameters"""
        # Setup mocks
        mock_habery_class.return_value = mock_habery
        mock_regery_class.return_value = mock_regery
        mock_habery.habByName.return_value = mock_hab
        mock_habery.name = "test-habery-name"

        # Mock hab.endsFor to return HTTP endpoint
        mock_hab.pre = "EBfdLv2XaD_HaABMmPWRVMdKWSm7xvlbemcRMT-HABPRE"
        mock_hab.endsFor.return_value = {
            "controller": {mock_hab.pre: {"http": "http://127.0.0.1:8080"}}
        }

        mock_sentinel_db_instance = Mock()
        mock_app_baser.return_value = mock_sentinel_db_instance

        # Execute
        await setup_local(**setup_params)

        # Verify AppBaser creation with habery name and export_dir
        mock_app_baser.assert_called_once_with(
            name="test-habery-name", headDirPath=setup_params["export_dir"]
        )

        # Verify sentinel_db is passed to FileWatchingService
        file_watching_call = mock_file_watching_service.call_args
        assert file_watching_call.kwargs["db"] == mock_sentinel_db_instance

    @pytest.mark.asyncio
    @patch("registrar.app.registraring.habbing.Habery")
    @patch("registrar.app.registraring.credentialing.Regery")
    @patch("registrar.app.registraring.RegistrarAPIService")
    @patch("registrar.app.registraring.SentinelConfig")
    @patch("registrar.app.registraring.RegistrarEventHandler")
    @patch("registrar.app.registraring.register_handler")
    @patch("registrar.app.registraring.AppBaser")
    @patch("registrar.app.registraring.FileWatchingService")
    async def test_setup_local_file_watching_service_parameters(
        self,
        mock_file_watching_service,
        mock_app_baser,
        mock_register_handler,
        mock_event_handler,
        mock_sentinel_config,
        mock_api_service,
        mock_regery_class,
        mock_habery_class,
        setup_params,
        mock_habery,
        mock_regery,
        mock_hab,
    ):
        """Test that FileWatchingService is created with all correct parameters"""
        # Setup mocks
        mock_habery_class.return_value = mock_habery
        mock_regery_class.return_value = mock_regery
        mock_habery.habByName.return_value = mock_hab

        # Mock hab.endsFor to return HTTP endpoint
        mock_hab.pre = "EBfdLv2XaD_HaABMmPWRVMdKWSm7xvlbemcRMT-HABPRE"
        mock_hab.endsFor.return_value = {
            "controller": {mock_hab.pre: {"http": "http://127.0.0.1:8080"}}
        }

        mock_sentinel_db_instance = Mock()
        mock_app_baser.return_value = mock_sentinel_db_instance

        # Execute
        await setup_local(**setup_params)

        # Verify FileWatchingService creation with all parameters
        mock_file_watching_service.assert_called_once_with(
            export_dir=setup_params["export_dir"],
            poll_interval=3.0,
            hby=mock_habery,
            rgy=mock_regery,
            db=mock_sentinel_db_instance,
        )
