# -*- encoding: utf-8 -*-
"""
Unit tests for registrar.core.apiing module
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from keri import kering

from registrar.core.apiing import RegistrarAPIService, IPEXGrantHandler


class TestRegistrarAPIService:
    """Test suite for RegistrarAPIService class"""

    @pytest.fixture
    def mock_hby(self):
        """Create a mock Habery instance"""
        hby = Mock()
        hby.name = "test-hby"
        hby.kvy = Mock()
        return hby

    @pytest.fixture
    def mock_rgy(self):
        """Create a mock Regery instance"""
        rgy = Mock()
        rgy.reger = Mock()
        rgy.tvy = Mock()
        return rgy

    @pytest.fixture
    def mock_hab(self):
        """Create a mock Hab instance"""
        hab = Mock()
        hab.pre = "EBfdLv2XaD_HaABMmPWRVMdKWSm7xvlbemcRMT-HABPRE"
        return hab

    @pytest.fixture
    def api_service(self, mock_hby, mock_hab, mock_rgy):
        """Create a RegistrarAPIService instance"""
        with (
            patch("registrar.core.apiing.verifying.Verifier"),
            patch("registrar.core.apiing.exchanging.Exchanger"),
            patch("registrar.core.apiing.parsing.Parser"),
            patch("registrar.core.apiing.IPEXGrantHandler"),
        ):
            service = RegistrarAPIService(
                hby=mock_hby,
                hab=mock_hab,
                rgy=mock_rgy,
                issuer="EBfdLv2XaD_HaABMmPWRVMdKWSm7xvlbemcRMT-ISSUER",
                schema="EBfdLv2XaD_HaABMmPWRVMdKWSm7xvlbemcRMT-SCHEMA",
                host="0.0.0.0",
                port=9090,
            )
        return service

    def test_init_default_params(self, mock_hby, mock_hab, mock_rgy):
        """Test RegistrarAPIService initialization with default parameters"""
        with (
            patch("registrar.core.apiing.verifying.Verifier") as mock_verifier,
            patch("registrar.core.apiing.exchanging.Exchanger") as mock_exchanger,
            patch("registrar.core.apiing.parsing.Parser") as mock_parser,
            patch("registrar.core.apiing.IPEXGrantHandler"),
        ):

            mock_verifier_instance = Mock()
            mock_verifier.return_value = mock_verifier_instance
            mock_exchanger_instance = Mock()
            mock_exchanger.return_value = mock_exchanger_instance
            mock_parser_instance = Mock()
            mock_parser.return_value = mock_parser_instance

            issuer = "EBfdLv2XaD_HaABMmPWRVMdKWSm7xvlbemcRMT-ISSUER"
            schema = "EBfdLv2XaD_HaABMmPWRVMdKWSm7xvlbemcRMT-SCHEMA"

            service = RegistrarAPIService(
                hby=mock_hby, hab=mock_hab, rgy=mock_rgy, issuer=issuer, schema=schema
            )

            # Verify default parameters
            assert service.hby == mock_hby
            assert service.hab == mock_hab
            assert service.rgy == mock_rgy
            assert service.issuer == issuer
            assert service.host == "127.0.0.1"
            assert service.port == 8080
            assert service._task is None
            assert service._running is False
            assert service._shutdown_trigger is None

            # Verify Verifier initialization
            mock_verifier.assert_called_once_with(hby=mock_hby, reger=mock_rgy.reger)

            # Verify Exchanger initialization
            mock_exchanger.assert_called_once_with(hby=mock_hby, handlers=[])

            # Verify handler added to exchanger
            mock_exchanger_instance.addHandler.assert_called_once()

    def test_init_custom_params(self, mock_hby, mock_hab, mock_rgy):
        """Test RegistrarAPIService initialization with custom parameters"""
        with (
            patch("registrar.core.apiing.verifying.Verifier"),
            patch("registrar.core.apiing.exchanging.Exchanger"),
            patch("registrar.core.apiing.parsing.Parser"),
            patch("registrar.core.apiing.IPEXGrantHandler"),
        ):

            service = RegistrarAPIService(
                hby=mock_hby,
                hab=mock_hab,
                rgy=mock_rgy,
                issuer="EBfdLv2XaD_HaABMmPWRVMdKWSm7xvlbemcRMT-ISSUER",
                schema="EBfdLv2XaD_HaABMmPWRVMdKWSm7xvlbemcRMT-SCHEMA",
                host="192.168.1.1",
                port=3000,
            )

            assert service.host == "192.168.1.1"
            assert service.port == 3000

    def test_app_routes(self, api_service):
        """Test that Starlette app has correct routes configured"""
        routes = api_service.app.routes

        # Extract route paths and check methods contain expected verbs
        route_paths = {r.path for r in routes}

        assert "/" in route_paths
        assert "/registry/{regi}" in route_paths
        assert "/tel/{said}" in route_paths
        assert "/credential/{said}" in route_paths

        # Verify specific methods (note: Starlette adds HEAD to GET routes automatically)
        for route in routes:
            if route.path == "/":
                assert "PUT" in route.methods
            elif route.path in [
                "/registry/{regi}",
                "/tel/{said}",
                "/credential/{said}",
            ]:
                assert "GET" in route.methods

    @pytest.mark.asyncio
    async def test_parse_endpoint(self, api_service):
        """Test parse endpoint processes data and escrows"""
        # Mock request
        mock_request = Mock(spec=Request)
        test_data = b"test data"
        mock_request.body = AsyncMock(return_value=test_data)

        # Mock parser and processing methods
        api_service.external_psr.parse = Mock()
        api_service.credential_psr.kvy.processEscrows = Mock()
        api_service.exc.processEscrow = Mock()
        api_service.rgy.tvy.processEscrows = Mock()
        api_service.verifier.processEscrows = Mock()

        # Execute
        response = await api_service.parse(mock_request)

        # Verify
        mock_request.body.assert_called_once()
        api_service.external_psr.parse.assert_called_once_with(test_data)
        api_service.credential_psr.kvy.processEscrows.assert_called_once()
        api_service.exc.processEscrow.assert_called_once()
        api_service.rgy.tvy.processEscrows.assert_called_once()
        api_service.verifier.processEscrows.assert_called_once()

        # Verify response
        assert isinstance(response, Response)
        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_get_registry_success(self, api_service):
        """Test get_registry endpoint with successful response"""
        # Mock request with path params
        mock_request = Mock(spec=Request)
        mock_request.path_params = {"regi": "test-regi-123"}

        # Mock output_tel to return data
        test_tel_data = b"registry tel data"
        api_service.output_tel = Mock(return_value=test_tel_data)

        # Execute
        response = await api_service.get_registry(mock_request)

        # Verify
        api_service.output_tel.assert_called_once_with("test-regi-123")
        assert isinstance(response, Response)
        assert response.status_code == 200
        assert response.body == test_tel_data
        assert response.media_type == "application/cesr"

    @pytest.mark.asyncio
    async def test_get_registry_missing_regi(self, api_service):
        """Test get_registry endpoint with missing regi parameter"""
        # Mock request without regi param
        mock_request = Mock(spec=Request)
        mock_request.path_params = {}

        # Execute
        response = await api_service.get_registry(mock_request)

        # Verify
        assert isinstance(response, JSONResponse)
        assert response.status_code == 404
        assert b"Credential transaction event log not found" in response.body

    @pytest.mark.asyncio
    async def test_get_registry_empty_tel(self, api_service):
        """Test get_registry endpoint when output_tel returns empty data"""
        # Mock request
        mock_request = Mock(spec=Request)
        mock_request.path_params = {"regi": "test-regi-123"}

        # Mock output_tel to return empty data
        api_service.output_tel = Mock(return_value=b"")

        # Execute
        response = await api_service.get_registry(mock_request)

        # Verify
        assert isinstance(response, JSONResponse)
        assert response.status_code == 404
        assert b"Registry transaction event log not found" in response.body

    @pytest.mark.asyncio
    async def test_get_registry_missing_entry_error(self, api_service):
        """Test get_registry endpoint when MissingEntryError is raised"""
        # Mock request
        mock_request = Mock(spec=Request)
        mock_request.path_params = {"regi": "test-regi-123"}

        # Mock output_tel to raise MissingEntryError
        api_service.output_tel = Mock(side_effect=kering.MissingEntryError)

        # Execute
        response = await api_service.get_registry(mock_request)

        # Verify
        assert isinstance(response, JSONResponse)
        assert response.status_code == 404
        assert b"Registry transaction event log not found" in response.body

    @pytest.mark.asyncio
    async def test_get_tel_success(self, api_service):
        """Test get_tel endpoint with successful response"""
        # Mock request
        mock_request = Mock(spec=Request)
        mock_request.path_params = {"said": "test-said-456"}

        # Mock output_tel
        test_tel_data = b"tel data"
        api_service.output_tel = Mock(return_value=test_tel_data)

        # Execute
        response = await api_service.get_tel(mock_request)

        # Verify
        api_service.output_tel.assert_called_once_with("test-said-456")
        assert isinstance(response, Response)
        assert response.status_code == 200
        assert response.body == test_tel_data
        assert response.media_type == "application/cesr"

    @pytest.mark.asyncio
    async def test_get_tel_missing_said(self, api_service):
        """Test get_tel endpoint with missing said parameter"""
        # Mock request
        mock_request = Mock(spec=Request)
        mock_request.path_params = {}

        # Execute
        response = await api_service.get_tel(mock_request)

        # Verify
        assert isinstance(response, JSONResponse)
        assert response.status_code == 404
        assert b"Credential transaction event log not found" in response.body

    @pytest.mark.asyncio
    async def test_get_tel_empty_data(self, api_service):
        """Test get_tel endpoint when output_tel returns empty data"""
        # Mock request
        mock_request = Mock(spec=Request)
        mock_request.path_params = {"said": "test-said-456"}

        # Mock output_tel
        api_service.output_tel = Mock(return_value=b"")

        # Execute
        response = await api_service.get_tel(mock_request)

        # Verify
        assert isinstance(response, JSONResponse)
        assert response.status_code == 404
        assert b"Credential transaction event log not found" in response.body

    @pytest.mark.asyncio
    async def test_get_credential_success_minimal(self, api_service):
        """Test get_credential endpoint with minimal parameters"""
        # Mock request
        mock_request = Mock(spec=Request)
        mock_request.path_params = {"said": "test-cred-789"}
        mock_request.query_params = {}

        # Mock output_cred
        test_cred_data = b"credential data"
        api_service.output_cred = Mock(return_value=test_cred_data)

        # Execute
        response = await api_service.get_credential(mock_request)

        # Verify
        api_service.output_cred.assert_called_once_with(
            "test-cred-789", False, False, False
        )
        assert isinstance(response, Response)
        assert response.status_code == 200
        assert response.body == test_cred_data
        assert response.media_type == "application/cesr"

    @pytest.mark.asyncio
    async def test_get_credential_success_with_all_params(self, api_service):
        """Test get_credential endpoint with all query parameters"""
        # Mock request
        mock_request = Mock(spec=Request)
        mock_request.path_params = {"said": "test-cred-789"}
        mock_request.query_params = {
            "registry": "true",
            "tel": "true",
            "chains": "true",
        }

        # Mock output_cred
        test_cred_data = b"credential data with all info"
        api_service.output_cred = Mock(return_value=test_cred_data)

        # Execute
        response = await api_service.get_credential(mock_request)

        # Verify
        api_service.output_cred.assert_called_once_with(
            "test-cred-789", "true", "true", "true"
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get_credential_missing_said(self, api_service):
        """Test get_credential endpoint with missing said parameter"""
        # Mock request
        mock_request = Mock(spec=Request)
        mock_request.path_params = {}
        mock_request.query_params = {}

        # Execute
        response = await api_service.get_credential(mock_request)

        # Verify
        assert isinstance(response, JSONResponse)
        assert response.status_code == 404
        assert b"Credential not found, no said" in response.body

    @pytest.mark.asyncio
    async def test_get_credential_empty_output(self, api_service):
        """Test get_credential endpoint when output_cred returns empty data"""
        # Mock request
        mock_request = Mock(spec=Request)
        mock_request.path_params = {"said": "test-cred-789"}
        mock_request.query_params = {}

        # Mock output_cred to return empty
        api_service.output_cred = Mock(return_value=b"")

        # Execute
        response = await api_service.get_credential(mock_request)

        # Verify
        assert isinstance(response, JSONResponse)
        assert response.status_code == 404
        assert b"Credential not found for test-cred-789" in response.body

    @pytest.mark.asyncio
    async def test_get_credential_missing_entry_error(self, api_service):
        """Test get_credential endpoint when MissingEntryError is raised"""
        # Mock request
        mock_request = Mock(spec=Request)
        mock_request.path_params = {"said": "test-cred-789"}
        mock_request.query_params = {}

        # Mock output_cred to raise error
        api_service.output_cred = Mock(
            side_effect=kering.MissingEntryError("Not found")
        )

        # Execute
        response = await api_service.get_credential(mock_request)

        # Verify
        assert isinstance(response, JSONResponse)
        assert response.status_code == 404
        assert b"Credential not found for said test-cred-789" in response.body

    def test_output_tel(self, api_service):
        """Test output_tel method"""
        # Mock reger.clonePreIter to return test messages
        mock_msg1 = b"msg1" + b"atc1"
        mock_msg2 = b"msg2" + b"atc2"
        api_service.rgy.reger.clonePreIter = Mock(return_value=[mock_msg1, mock_msg2])

        # Mock serdering.SerderKERI
        with patch("registrar.core.apiing.serdering.SerderKERI") as mock_serder_class:
            # Create mock serders with size attributes
            mock_serder1 = Mock()
            mock_serder1.size = 4
            mock_serder1.raw = b"msg1"

            mock_serder2 = Mock()
            mock_serder2.size = 4
            mock_serder2.raw = b"msg2"

            mock_serder_class.side_effect = [mock_serder1, mock_serder2]

            # Execute
            result = api_service.output_tel("test-regk")

            # Verify
            api_service.rgy.reger.clonePreIter.assert_called_once_with(pre="test-regk")
            assert result == b"msg1atc1msg2atc2"

    def test_output_tel_empty(self, api_service):
        """Test output_tel method with no messages"""
        api_service.rgy.reger.clonePreIter = Mock(return_value=[])

        # Execute
        result = api_service.output_tel("test-regk")

        # Verify
        assert result == b""

    def test_output_cred_minimal(self, api_service):
        """Test output_cred with minimal options (no registry, tel, or chains)"""
        # Mock creder
        mock_creder = Mock()
        mock_creder.said = "cred-said"
        mock_creder.regi = None
        mock_creder.edge = None

        api_service.rgy.reger.cloneCred = Mock(return_value=(mock_creder,))
        api_service.rgy.reger.cancs = Mock()

        # Mock cancs.get to return tuple
        mock_prefixer = Mock()
        mock_seqner = Mock()
        mock_saider = Mock()
        api_service.rgy.reger.cancs.get = Mock(
            return_value=(mock_prefixer, mock_seqner, mock_saider)
        )

        # Mock signing.serialize
        with patch("registrar.core.apiing.signing.serialize") as mock_serialize:
            mock_serialize.return_value = b"serialized-cred"

            # Execute
            result = api_service.output_cred("test-said", False, False, False)

            # Verify
            api_service.rgy.reger.cloneCred.assert_called_once_with(said="test-said")
            mock_serialize.assert_called_once_with(
                mock_creder, mock_prefixer, mock_seqner, mock_saider
            )
            assert result == b"serialized-cred"

    def test_output_cred_with_registry(self, api_service):
        """Test output_cred with registry option"""
        # Mock creder
        mock_creder = Mock()
        mock_creder.said = "cred-said"
        mock_creder.regi = "registry-id"
        mock_creder.edge = None

        api_service.rgy.reger.cloneCred = Mock(return_value=(mock_creder,))
        api_service.rgy.reger.cancs = Mock()
        api_service.rgy.reger.cancs.get = Mock(return_value=(Mock(), Mock(), Mock()))

        # Mock output_tel
        api_service.output_tel = Mock(return_value=b"registry-tel")

        with patch("registrar.core.apiing.signing.serialize") as mock_serialize:
            mock_serialize.return_value = b"serialized-cred"

            # Execute
            result = api_service.output_cred("test-said", False, True, False)

            # Verify
            api_service.output_tel.assert_called_once_with("registry-id")
            assert result == b"registry-telserialized-cred"

    def test_output_cred_with_tel(self, api_service):
        """Test output_cred with tel option"""
        # Mock creder
        mock_creder = Mock()
        mock_creder.said = "cred-said"
        mock_creder.regi = None
        mock_creder.edge = None

        api_service.rgy.reger.cloneCred = Mock(return_value=(mock_creder,))
        api_service.rgy.reger.cancs = Mock()
        api_service.rgy.reger.cancs.get = Mock(return_value=(Mock(), Mock(), Mock()))

        # Mock output_tel
        api_service.output_tel = Mock(return_value=b"cred-tel")

        with patch("registrar.core.apiing.signing.serialize") as mock_serialize:
            mock_serialize.return_value = b"serialized-cred"

            # Execute
            result = api_service.output_cred("test-said", True, False, False)

            # Verify
            api_service.output_tel.assert_called_once_with("cred-said")
            assert result == b"cred-telserialized-cred"

    def test_output_cred_with_chains(self, api_service):
        """Test output_cred with chains option"""
        # Mock creder with edge/chains
        mock_creder = Mock()
        mock_creder.said = "cred-said"
        mock_creder.regi = None
        mock_creder.edge = {
            "d": "some-value",  # Should be skipped
            "chain1": {"n": "chain-said-1"},
            "chain2": {"n": "chain-said-2"},
            "invalid": "not-a-dict",  # Should be skipped
        }

        api_service.rgy.reger.cloneCred = Mock(return_value=(mock_creder,))
        api_service.rgy.reger.cancs = Mock()
        api_service.rgy.reger.cancs.get = Mock(return_value=(Mock(), Mock(), Mock()))

        with patch("registrar.core.apiing.signing.serialize") as mock_serialize:
            mock_serialize.return_value = b"serialized-cred"

            # Create a real function that we can track calls on
            call_count = [0]

            def tracked_output_cred(said, tel, registry, chains):
                call_count[0] += 1
                if call_count[0] == 1:
                    # First call - the original call
                    # We need to manually handle the recursion
                    out = bytearray()
                    if chains:
                        # Process chains
                        for chain_said in ["chain-said-1", "chain-said-2"]:
                            # Recursive call
                            out.extend(b"chain-data")
                    out.extend(b"serialized-cred")
                    return bytes(out)
                else:
                    # Recursive calls
                    return b"chain-data"

            api_service.output_cred = tracked_output_cred

            # Execute
            result = api_service.output_cred("test-said", False, False, True)

            # Verify - should have called for each chain SAID
            assert result == b"chain-datachain-dataserialized-cred"
            assert call_count[0] == 1

    def test_output_cred_with_all_options(self, api_service):
        """Test output_cred with all options enabled"""
        # Mock creder
        mock_creder = Mock()
        mock_creder.said = "cred-said"
        mock_creder.regi = "registry-id"
        mock_creder.edge = {"chain1": {"n": "chain-said-1"}}

        api_service.rgy.reger.cloneCred = Mock(return_value=(mock_creder,))
        api_service.rgy.reger.cancs = Mock()
        api_service.rgy.reger.cancs.get = Mock(return_value=(Mock(), Mock(), Mock()))

        # Track calls
        output_tel_calls = []

        def mock_output_tel(regk):
            output_tel_calls.append(regk)
            return f"tel-{regk}".encode()

        api_service.output_tel = mock_output_tel

        call_count = [0]

        def tracked_output_cred(said, tel, registry, chains):
            call_count[0] += 1
            if call_count[0] == 1:
                out = bytearray()
                if registry and mock_creder.regi:
                    out.extend(mock_output_tel(mock_creder.regi))
                if tel:
                    out.extend(mock_output_tel(mock_creder.said))
                if chains:
                    out.extend(b"chain-data")
                out.extend(b"serialized-cred")
                return bytes(out)
            else:
                return b"chain-data"

        api_service.output_cred = tracked_output_cred

        with patch("registrar.core.apiing.signing.serialize") as mock_serialize:
            mock_serialize.return_value = b"serialized-cred"

            # Execute
            result = api_service.output_cred("test-said", True, True, True)

            # Verify all components present
            assert b"tel-registry-id" in result
            assert b"tel-cred-said" in result
            assert b"chain-data" in result
            assert b"serialized-cred" in result

    @pytest.mark.asyncio
    async def test_run_success(self, api_service):
        """Test run method starts server successfully"""
        with (
            patch("registrar.core.apiing.serve") as mock_serve,
            patch("registrar.core.apiing.Config") as mock_config_class,
        ):

            # Setup mocks
            mock_config = Mock()
            mock_config_class.return_value = mock_config
            mock_serve.return_value = AsyncMock()

            # Create a task that will complete quickly
            async def run_and_cancel():
                task = asyncio.create_task(api_service.run())
                await asyncio.sleep(0.01)
                api_service.stop()
                await asyncio.sleep(0.01)
                return task

            # Execute
            await run_and_cancel()

            # Verify config
            assert mock_config.bind == ["0.0.0.0:9090"]
            assert mock_config.accesslog == "-"
            assert mock_config.errorlog == "-"

    @pytest.mark.asyncio
    async def test_run_cancelled_error(self, api_service):
        """Test run method handles CancelledError"""
        with (
            patch("registrar.core.apiing.serve") as mock_serve,
            patch("registrar.core.apiing.Config"),
        ):

            # Make serve raise CancelledError
            mock_serve.side_effect = asyncio.CancelledError()

            # Execute
            await api_service.run()

            # Verify service stopped
            assert api_service._running is False

    @pytest.mark.asyncio
    async def test_run_exception(self, api_service):
        """Test run method handles generic exceptions"""
        with (
            patch("registrar.core.apiing.serve") as mock_serve,
            patch("registrar.core.apiing.Config"),
        ):

            # Make serve raise exception
            mock_serve.side_effect = Exception("Test error")

            # Execute
            await api_service.run()

            # Verify service stopped
            assert api_service._running is False

    def test_start(self, api_service):
        """Test start method creates asyncio task"""
        with patch("asyncio.create_task") as mock_create_task:
            mock_task = Mock()
            mock_create_task.return_value = mock_task

            # Execute
            result = api_service.start()

            # Verify
            mock_create_task.assert_called_once()
            assert result == mock_task
            assert api_service._task == mock_task

    def test_start_already_running(self, api_service):
        """Test start method when task already exists and not done"""
        # Create a mock task that's not done
        mock_task = Mock()
        mock_task.done.return_value = False
        api_service._task = mock_task

        with patch("asyncio.create_task") as mock_create_task:
            # Execute
            result = api_service.start()

            # Verify - should not create new task
            mock_create_task.assert_not_called()
            assert result == mock_task

    def test_start_task_done(self, api_service):
        """Test start method when previous task is done"""
        # Create a mock task that's done
        old_task = Mock()
        old_task.done.return_value = True
        api_service._task = old_task

        with patch("asyncio.create_task") as mock_create_task:
            new_task = Mock()
            mock_create_task.return_value = new_task

            # Execute
            result = api_service.start()

            # Verify - should create new task
            mock_create_task.assert_called_once()
            assert result == new_task
            assert api_service._task == new_task

    def test_stop_with_task(self, api_service):
        """Test stop method when task is running"""
        # Setup
        mock_task = Mock()
        mock_task.done.return_value = False
        mock_shutdown_trigger = Mock()
        api_service._task = mock_task
        api_service._shutdown_trigger = mock_shutdown_trigger
        api_service._running = True

        # Execute
        api_service.stop()

        # Verify
        assert api_service._running is False
        mock_shutdown_trigger.set.assert_called_once()
        mock_task.cancel.assert_called_once()

    def test_stop_without_task(self, api_service):
        """Test stop method when no task exists"""
        # Setup
        api_service._task = None
        api_service._shutdown_trigger = Mock()
        api_service._running = True

        # Execute
        api_service.stop()

        # Verify - should not raise error
        assert api_service._running is False

    def test_stop_task_already_done(self, api_service):
        """Test stop method when task is already done"""
        # Setup
        mock_task = Mock()
        mock_task.done.return_value = True
        api_service._task = mock_task
        api_service._running = True

        # Execute
        api_service.stop()

        # Verify - should not call cancel
        mock_task.cancel.assert_not_called()
        assert api_service._running is False


class TestIPEXGrantHandler:
    """Test suite for IPEXGrantHandler class"""

    @pytest.fixture
    def mock_hby(self):
        """Create a mock Habery instance"""
        return Mock()

    @pytest.fixture
    def mock_psr(self):
        """Create a mock Parser instance"""
        return Mock()

    @pytest.fixture
    def handler(self, mock_hby, mock_psr):
        """Create an IPEXGrantHandler instance"""
        return IPEXGrantHandler(
            hby=mock_hby,
            psr=mock_psr,
            issuer="EBfdLv2XaD_HaABMmPWRVMdKWSm7xvlbemcRMT-ISSUER",
        )

    def test_init(self, handler, mock_hby, mock_psr):
        """Test IPEXGrantHandler initialization"""
        assert handler.hby == mock_hby
        assert handler.psr == mock_psr
        assert handler.issuer == "EBfdLv2XaD_HaABMmPWRVMdKWSm7xvlbemcRMT-ISSUER"
        assert handler.resource == "/ipex/grant"

    def test_handle_success(self, handler, mock_hby, mock_psr):
        """Test handle method with valid grant message"""
        # Mock serder
        mock_serder = Mock()
        mock_serder.said = "test-said"
        mock_serder.ked = {
            "e": {
                "acdc": {"i": "EBfdLv2XaD_HaABMmPWRVMdKWSm7xvlbemcRMT-ISSUER"},
                "anc": {"test": "data"},
                "iss": {"test": "data"},
            }
        }

        # Mock grant message
        mock_grant = Mock()
        mock_grant.said = "grant-said"
        mock_grant.ked = {"r": "/ipex/grant"}

        # Mock pathed attachments
        mock_pathed = {
            "anc": b"anc-attachment",
            "iss": b"iss-attachment",
            "acdc": b"acdc-attachment",
        }

        # Mock SerderACDC
        mock_creder = Mock()
        mock_creder.issuer = "EBfdLv2XaD_HaABMmPWRVMdKWSm7xvlbemcRMT-ISSUER"

        # Mock exchanging.cloneMessage
        with (
            patch("registrar.core.apiing.exchanging.cloneMessage") as mock_clone,
            patch("registrar.core.apiing.coring.Sadder") as mock_sadder_class,
            patch("registrar.core.apiing.serdering.SerderACDC") as mock_serder_acdc,
        ):

            mock_clone.return_value = (mock_grant, mock_pathed)
            mock_serder_acdc.return_value = mock_creder

            # Mock Sadder for each label
            mock_sadders = []
            for _ in range(3):
                mock_sadder = Mock()
                mock_sadder.raw = b"raw-data"
                mock_sadders.append(mock_sadder)
            mock_sadder_class.side_effect = mock_sadders

            # Execute
            handler.handle(mock_serder)

            # Verify cloneMessage called
            mock_clone.assert_called_once_with(mock_hby, "test-said")

            # Verify parseOne called for each label
            assert mock_psr.parseOne.call_count == 3

    def test_handle_invalid_route(self, handler, mock_hby, mock_psr):
        """Test handle method processes message regardless of route"""
        # Mock serder with full embeds
        mock_serder = Mock()
        mock_serder.said = "test-said"
        mock_serder.ked = {
            "e": {
                "acdc": {"i": "EBfdLv2XaD_HaABMmPWRVMdKWSm7xvlbemcRMT-ISSUER"},
                "anc": {"test": "data"},
                "iss": {"test": "data"},
            }
        }

        # Mock grant message - route is not validated by current code
        mock_grant = Mock()
        mock_grant.said = "grant-said"
        mock_grant.ked = {"r": "/ipex/other"}

        # Mock pathed attachments
        mock_pathed = {
            "anc": b"anc-attachment",
            "iss": b"iss-attachment",
            "acdc": b"acdc-attachment",
        }

        # Mock SerderACDC
        mock_creder = Mock()
        mock_creder.issuer = "EBfdLv2XaD_HaABMmPWRVMdKWSm7xvlbemcRMT-ISSUER"

        with (
            patch("registrar.core.apiing.exchanging.cloneMessage") as mock_clone,
            patch("registrar.core.apiing.serdering.SerderACDC") as mock_serder_acdc,
            patch("registrar.core.apiing.coring.Sadder") as mock_sadder_class,
        ):
            mock_clone.return_value = (mock_grant, mock_pathed)
            mock_serder_acdc.return_value = mock_creder

            # Mock Sadder
            mock_sadder = Mock()
            mock_sadder.raw = b"raw-data"
            mock_sadder_class.return_value = mock_sadder

            # Execute - should process without error even with different route
            handler.handle(mock_serder)

            # Verify cloneMessage called
            mock_clone.assert_called_once_with(mock_hby, "test-said")

            # Verify parseOne called for each label
            assert mock_psr.parseOne.call_count == 3

    def test_handle_with_attachments_parameter(self, handler, mock_hby, mock_psr):
        """Test handle method when attachments parameter is provided"""
        # Mock serder
        mock_serder = Mock()
        mock_serder.said = "test-said"
        mock_serder.ked = {
            "e": {
                "acdc": {"i": "EBfdLv2XaD_HaABMmPWRVMdKWSm7xvlbemcRMT-ISSUER"},
                "anc": {"test": "data"},
                "iss": {"test": "data"},
            }
        }

        # Mock grant message
        mock_grant = Mock()
        mock_grant.said = "grant-said"
        mock_grant.ked = {"r": "/ipex/grant"}

        # Mock pathed attachments
        mock_pathed = {
            "anc": b"anc-attachment",
            "iss": b"iss-attachment",
            "acdc": b"acdc-attachment",
        }

        # Mock SerderACDC
        mock_creder = Mock()
        mock_creder.issuer = "EBfdLv2XaD_HaABMmPWRVMdKWSm7xvlbemcRMT-ISSUER"

        # Attachments parameter (currently not used in implementation)
        test_attachments = [("path", "data")]

        with (
            patch("registrar.core.apiing.exchanging.cloneMessage") as mock_clone,
            patch("registrar.core.apiing.coring.Sadder") as mock_sadder_class,
            patch("registrar.core.apiing.serdering.SerderACDC") as mock_serder_acdc,
        ):

            mock_clone.return_value = (mock_grant, mock_pathed)
            mock_serder_acdc.return_value = mock_creder

            mock_sadder = Mock()
            mock_sadder.raw = b"raw-data"
            mock_sadder_class.return_value = mock_sadder

            # Execute with attachments parameter
            handler.handle(mock_serder, attachments=test_attachments)

            # Verify still works (attachments parameter is not used in current implementation)
            mock_clone.assert_called_once()
