# -*- encoding: utf-8 -*-
"""
keriguard.core.initializing module

Methods for initializing a KERIGuard instance

"""

import re
from pathlib import Path
from typing import Dict, Any
from urllib.parse import urlparse

import requests
import yaml
from keri.app import connecting

# Regex pattern to extract AID/prefix from OOBI URL
# Matches: /oobi/{cid} or /oobi/{cid}/{role} or /oobi/{cid}/{role}/{eid}
OOBI_RE = re.compile(
    r"\A/oobi/(?P<cid>[^/]+)(?:/(?P<role>[^/]+)(?:/(?P<eid>[^/]+))?)?\Z", re.IGNORECASE
)


def load_oobi(hby, oobi: str, alias: str):
    org = connecting.Organizer(hby=hby)
    purl = urlparse(oobi)
    match = OOBI_RE.match(purl.path)
    if not match:
        raise ValueError(f"Invalid OOBI URL {oobi}")

    aid = match.group("cid")

    response = requests.get(oobi)
    response.raise_for_status()

    hby.psr.parse(ims=response.content)
    if aid not in hby.kevers:
        raise ValueError(f"Invalid OOBI URL {oobi} for {aid}")

    hby.kvy.processEscrows()
    org.update(pre=aid, data=dict(alias=alias, oobi=oobi))

    return aid


class IssuerConfig:
    """Configuration for the issuer."""

    def __init__(self, data: Dict[str, Any]):
        self._data = data

    @property
    def aid(self) -> str:
        """The issuer's AID."""
        return self._data.get("aid", "")

    @property
    def oobi(self) -> str:
        """The issuer's OOBI URL."""
        return self._data.get("oobi", "")


class RegistrarConfig:
    """
    Configuration loader and accessor for KERIGuard initialization.

    This class reads a YAML configuration file and provides typed access
    to all configuration values needed for initializing a KERIGuard instance.

    Example:
        config = KeriguardConfig.load("/path/to/keriguard.conf")
        print(config.registrar.aid)
        print(config.registrar.keriguard.oobi)
        print(config.issuer.aid)
    """

    def __init__(self, data: Dict[str, Any]):
        self._data = data
        self._issuer = IssuerConfig(data.get("issuer", {}))

    @classmethod
    def load(cls, config_path: str) -> "RegistrarConfig":
        """
        Load configuration from a YAML file.

        Args:
            config_path: Path to the YAML configuration file

        Returns:
            KeriguardConfig instance with loaded configuration

        Raises:
            FileNotFoundError: If the configuration file doesn't exist
            yaml.YAMLError: If the YAML is malformed
        """
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        with open(path, "r") as f:
            data = yaml.safe_load(f)

        if data is None:
            data = {}

        return cls(data)

    @property
    def url(self) -> str:
        """The registrar URL."""
        return self._data.get("url", "")

    @property
    def issuer(self) -> IssuerConfig:
        """The issuer configuration."""
        return self._issuer
