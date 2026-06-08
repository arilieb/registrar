# Registrar

A KERI credential and transaction event log service for managing verifiable credentials, registry data, and contact information in the KERI (Key Event Receipt Infrastructure) ecosystem.

## Overview

Registrar is a Python-based service that provides a REST API for serving KERI credentials, transaction event logs (TELs), and registry data. It integrates with the [Sentinel](https://github.com/healthKERI/sentinel) framework to monitor and process KERI events, enabling automated credential management and contact tracking.

### Key Features

- **REST API**: HTTP endpoints for accessing credentials, TELs, and registry data
- **Event Processing**: Real-time monitoring and processing of KERI events (KEL, TEL, Credentials)
- **IPEX Protocol Support**: Handle IPEX grant messages for credential exchange
- **Contact Management**: Track and manage KERI contacts with OOBI (Out-of-Band Introduction) support
- **CESR Format**: Native support for CESR (Composable Event Streaming Representation) data format
- **Credential Validation**: Verify credentials against authorized issuers and schemas

## Architecture

```
┌─────────────────────────────────────────┐
│         Registrar CLI                   │
│  (Command line interface)               │
└────────────────┬────────────────────────┘
                 │
    ┌────────────┴────────────┐
    │                         │
┌───▼──────────────┐  ┌───────▼─────────────┐
│ API Service      │  │ Sentinel Service    │
│ (REST endpoints) │  │ (File watching)     │
│                  │  │                     │
│ - /registry/{id} │  │ - KEL events        │
│ - /tel/{id}      │  │ - TEL events        │
│ - /credential/   │  │ - Credential events │
│ - /oobi/{aid}    │  │                     │
│ - PUT /          │  │                     │
└──────────────────┘  └─────────────────────┘
         │                     │
         └──────────┬──────────┘
                    │
         ┌──────────▼──────────┐
         │   KERI Core         │
         │   - Habery (hby)    │
         │   - Registry (rgy)  │
         │   - Organizer (org) │
         └─────────────────────┘
```

## Installation

### Prerequisites

- Python 3.13.3 or higher
- Git (for dependency installation)

### Install from Source

```bash
git clone https://github.com/healthKERI/registrar.git
cd registrar
pip install -e .
```

### Install from PyPI

```bash
pip install registrar
```

## Usage

### Starting the Registrar Service

```bash
registrar start \
  --name my-registrar \
  --alias my-identifier \
  --issuer <QB64-AID-of-authorized-issuer> \
  --passcode <22-character-passcode> \
  --base /path/to/keri/keystore \
  --schema <credential-schema-SAID> \
  --sentinel-export-dir /path/to/sentinel/exports
```

### Command Line Options

| Option | Short | Required | Description |
|--------|-------|----------|-------------|
| `--name` | `-n` | Yes | Name of the database environment |
| `--alias` | `-a` | Yes | Human-readable alias for the identifier prefix |
| `--issuer` | `-I` | Yes | QB64 AID of the authorized credential issuer |
| `--passcode` | `-p` | No | 22-character encryption passcode for keystore |
| `--base` | `-b` | No | Optional prefix to file location of KERI keystore |
| `--schema` | `-S` | No | Schema SAID for valid authorization credentials |
| `--sentinel-export-dir` | `-e` | No | Directory for exported CESR files (default: `/usr/local/sentinel`) |
| `--loglevel` | | No | Set log level: DEBUG, INFO, WARNING, ERROR, CRITICAL (default: INFO) |
| `--logfile` | | No | Path to log file (logs to console if not specified) |

### Example

```bash
registrar start \
  --name healthkeri-registrar \
  --alias registrar-001 \
  --issuer EBjNDLqnuiGMEzfUvd22GdZ7MixOGDM7jMcZXwGcvV5p \
  --passcode 0123456789abcdefghijkl \
  --schema EBfdlu8R27Fbx-ehrqwImnK-8Cm79sqbAQ4MmvEAYqao \
  --loglevel INFO
```

## API Endpoints

Once running, Registrar exposes the following HTTP endpoints:

### GET /registry/{regi}

Retrieve the transaction event log for a specific registry.

**Response**: CESR-encoded registry TEL

```bash
curl http://localhost:8080/registry/EBfdlu8R27Fbx-ehrqwImnK-8Cm79sqbAQ4MmvEAYqao
```

### GET /tel/{said}

Retrieve the transaction event log for a specific credential or registry.

**Response**: CESR-encoded TEL data

```bash
curl http://localhost:8080/tel/ECui4-TJf1ViYzBLWYXqTGYJG7F3ROdpB6GXxVpZ0pQp
```

### GET /credential/{said}

Retrieve a credential by its SAID (Self-Addressing Identifier).

**Query Parameters**:
- `registry` (boolean): Include registry TEL
- `tel` (boolean): Include credential TEL
- `chains` (boolean): Include chained credentials

**Response**: CESR-encoded credential data

```bash
# Get credential with TEL and registry
curl "http://localhost:8080/credential/ECui4-TJf1ViYzBLWYXqTGYJG7F3ROdpB6GXxVpZ0pQp?tel=true&registry=true"
```

### GET /oobi/{aid}

Retrieve the OOBI (Out-of-Band Introduction) URL for a contact by their AID.

**Response**: JSON with OOBI URL

```bash
curl http://localhost:8080/oobi/EBjNDLqnuiGMEzfUvd22GdZ7MixOGDM7jMcZXwGcvV5p
```

Example response:
```json
{
  "url": "http://example.com:5642/oobi/EBjNDLqnuiGMEzfUvd22GdZ7MixOGDM7jMcZXwGcvV5p"
}
```

### PUT /

Parse and process KERI events (KEL, TEL, credentials) sent as CESR data.

**Request Body**: CESR-encoded event data

**Response**: 204 No Content on success

```bash
curl -X PUT http://localhost:8080/ \
  -H "Content-Type: application/cesr" \
  --data-binary "@event.cesr"
```

## Event Processing

Registrar uses the Sentinel framework to monitor and process KERI events:

### KEL Events (Key Event Log)
- Monitor changes to KERI key states
- Track identifier rotations and updates

### TEL Events (Transaction Event Log)
- Process transaction-based state changes
- Track credential status updates (issuance, revocation)

### Credential Events
- Handle credential issuance and validation
- Process IPEX grant messages
- Verify credentials against authorized issuers

## Configuration

### KERI Configuration

Registrar requires a KERI habitat (hab) configuration with an HTTP endpoint location. Example configuration structure:

```json
{
  "controller": {
    "<your-AID>": {
      "http": "http://localhost:8080"
    }
  }
}
```

### Sentinel Integration

The service monitors a directory for CESR files exported by Sentinel:
- Default location: `/usr/local/sentinel`
- Poll interval: 3.0 seconds
- Automatically processes new files as they appear

## Development

### Project Structure

```
registrar/
├── src/
│   └── registrar/
│       ├── app/
│       │   ├── cli/              # Command line interface
│       │   │   ├── commands/
│       │   │   │   └── start.py  # Start command
│       │   │   └── registrar.py  # CLI entry point
│       │   └── registraring.py   # Service setup
│       └── core/
│           ├── apiing.py         # REST API service
│           ├── authing.py        # Authentication logic
│           ├── serving.py        # Server utilities
│           └── sentinel/
│               ├── handler.py    # Event handler
│               ├── config.py     # Configuration
│               └── handlers/
│                   └── kel_handler.py  # KEL event processor
├── tests/                        # Test suite
├── scripts/                      # Utility scripts and data
├── pyproject.toml               # Python project configuration
└── LICENSE                      # Apache 2.0 license
```

### Running Tests

```bash
pip install -e ".[test]"
pytest
```

### Running with Coverage

```bash
pytest --cov=registrar --cov-report=html
```

### Code Quality

The project uses standard Python tools:
- **pytest**: Testing framework
- **ruff**: Linting and formatting

## Dependencies

### Core Dependencies
- **keri** (~1.3.4): KERI protocol implementation
- **sentinel**: Event monitoring framework
- **starlette** (0.52.1): ASGI web framework
- **hypercorn** (>=0.18.0): ASGI server
- **httpx** (>=0.28.1): HTTP client
- **cbor** (>=1.0.0): CBOR encoding/decoding
- **multicommand** (>=1.0.0): Multi-command CLI support

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Support

For issues, questions, or contributions:
- **Issues**: [GitHub Issues](https://github.com/healthKERI/registrar/issues)
- **Email**: phil@healthKERI.com

## Related Projects

- [KERI](https://github.com/WebOfTrust/keripy) - Key Event Receipt Infrastructure
- [Sentinel](https://github.com/healthKERI/sentinel) - KERI event monitoring framework

## Acknowledgments

Built on the KERI protocol and Sentinel framework by the healthKERI team.
