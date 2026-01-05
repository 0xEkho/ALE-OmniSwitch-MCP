"""Zone-based authentication for multi-site AOS deployments.

Supports global credentials with per-zone fallback based on IP subnet.
Zone ID is extracted from the second octet of the IP address.
Example: 10.9.x.x → Zone 9, 10.1.x.x → Zone 1
"""

import logging
import os
import re
from typing import Optional, List, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ZoneCredentials:
    """Credentials for a specific zone or global."""
    username: Optional[str] = None
    password: Optional[str] = None
    zone_id: Optional[int] = None  # None for global


def extract_zone_from_ip(host: str) -> Optional[int]:
    """Extract zone ID from IP address (second octet).
    
    Args:
        host: IP address or hostname
        
    Returns:
        Zone ID (1-255) or None if not a valid IP or can't extract
        
    Examples:
        10.9.5.10 → 9
        10.1.5.10 → 1
        192.168.1.1 → 168
        switch.example.com → None
    """
    # Match IPv4 address
    match = re.match(r'^(\d+)\.(\d+)\.(\d+)\.(\d+)$', host)
    if not match:
        logger.debug(f"Host '{host}' is not a valid IPv4, cannot extract zone")
        return None
    
    octets = [int(x) for x in match.groups()]
    if any(o < 0 or o > 255 for o in octets):
        logger.debug(f"Host '{host}' has invalid octets")
        return None
    
    zone_id = octets[1]  # Second octet
    logger.debug(f"Extracted zone {zone_id} from IP {host}")
    return zone_id


class ZoneAuthResolver:
    """Resolves credentials based on zone configuration."""
    
    def __init__(self, zone_config: Optional[dict] = None):
        """Initialize resolver with zone configuration.
        
        Args:
            zone_config: Dictionary with 'global' and 'zones' keys:
                {
                    'global': {'username_env': 'VAR', 'password_env': 'VAR'},
                    'zones': {
                        9: {'username_env': 'VAR', 'password_env': 'VAR'},
                        1: {'username_env': 'VAR', 'password_env': 'VAR'}
                    }
                }
        """
        self.zone_config = zone_config or {}
        self._log_config()
    
    def _log_config(self):
        """Log configured zones for debugging."""
        if not self.zone_config:
            logger.info("Zone authentication disabled (no config)")
            return
        
        global_cfg = self.zone_config.get('global', {})
        zones_cfg = self.zone_config.get('zones', {})
        
        if global_cfg:
            logger.info(f"Global credentials: username_env={global_cfg.get('username_env')}, "
                       f"password_env={global_cfg.get('password_env')}")
        
        if zones_cfg:
            logger.info(f"Zone-specific credentials configured for zones: {list(zones_cfg.keys())}")
    
    def _resolve_credentials(self, config: dict) -> ZoneCredentials:
        """Resolve credentials from config with env var lookup.
        
        Args:
            config: Dict with username_env, password_env, username, password
            
        Returns:
            ZoneCredentials with resolved values
        """
        username = None
        password = None
        
        # Try env vars first
        if config.get('username_env'):
            username = os.environ.get(config['username_env'])
            if username:
                logger.debug(f"Resolved username from env: {config['username_env']}")
        
        # Fallback to direct value
        if not username and config.get('username'):
            username = config['username']
            logger.debug("Using direct username from config")
        
        # Same for password
        if config.get('password_env'):
            password = os.environ.get(config['password_env'])
            if password:
                logger.debug(f"Resolved password from env: {config['password_env']}")
        
        if not password and config.get('password'):
            password = config['password']
            logger.debug("Using direct password from config")
        
        return ZoneCredentials(username=username, password=password)
    
    def get_credentials_for_host(self, host: str) -> List[ZoneCredentials]:
        """Get ordered list of credentials to try for a host.
        
        Returns list in priority order:
        1. Global credentials (try first)
        2. Zone-specific credentials (fallback)
        
        Args:
            host: IP address or hostname
            
        Returns:
            List of ZoneCredentials to try (may be empty if no config)
        """
        if not self.zone_config:
            logger.debug("No zone config, returning empty credentials list")
            return []
        
        credentials_list = []
        
        # 1. Global credentials (highest priority)
        global_cfg = self.zone_config.get('global')
        if global_cfg:
            global_creds = self._resolve_credentials(global_cfg)
            if global_creds.username and global_creds.password:
                global_creds.zone_id = None  # Mark as global
                credentials_list.append(global_creds)
                logger.debug(f"Added global credentials for {host}")
        
        # 2. Zone-specific credentials (fallback)
        zone_id = extract_zone_from_ip(host)
        if zone_id is not None:
            zones_cfg = self.zone_config.get('zones', {})
            zone_cfg = zones_cfg.get(zone_id)
            
            if zone_cfg:
                zone_creds = self._resolve_credentials(zone_cfg)
                if zone_creds.username and zone_creds.password:
                    zone_creds.zone_id = zone_id
                    credentials_list.append(zone_creds)
                    logger.debug(f"Added zone {zone_id} credentials for {host}")
                else:
                    logger.warning(f"Zone {zone_id} configured but credentials not resolved")
            else:
                logger.debug(f"No specific credentials configured for zone {zone_id}")
        
        if not credentials_list:
            logger.warning(f"No credentials resolved for host {host}")
        else:
            logger.info(f"Resolved {len(credentials_list)} credential(s) for {host}")
        
        return credentials_list
    
    def get_primary_credentials(self, host: str) -> Optional[Tuple[str, str]]:
        """Get primary (first) credentials for a host.
        
        Args:
            host: IP address or hostname
            
        Returns:
            Tuple of (username, password) or None if no credentials
        """
        creds_list = self.get_credentials_for_host(host)
        if not creds_list:
            return None
        
        primary = creds_list[0]
        return (primary.username, primary.password)
