"""
Utility functions for benchmark module.
Separated to avoid circular imports.
"""

import socket
import platform
import os
import re
import base64
from datetime import datetime
from typing import Dict


def get_machine_info() -> Dict[str, str]:
    """
    Get machine information for report context.
    
    Returns:
        Dictionary with machine details including:
        - hostname: Machine hostname
        - ip_address: Local IP address
        - region: AWS region (if on EC2) or 'local'
        - instance_id: EC2 instance ID (if on EC2)
        - platform: OS platform info
    """
    info = {
        "hostname": socket.gethostname(),
        "platform": f"{platform.system()} {platform.release()}",
        "region": "unknown",
        "instance_id": "N/A",
        "availability_zone": "N/A",
    }
    
    # Try to get local IP
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        info["ip_address"] = s.getsockname()[0]
        s.close()
    except Exception:
        info["ip_address"] = "127.0.0.1"
    
    # Try to get AWS EC2 metadata (IMDSv2)
    try:
        import urllib.request
        
        # First get token for IMDSv2
        token_request = urllib.request.Request(
            "http://169.254.169.254/latest/api/token",
            method="PUT",
            headers={"X-aws-ec2-metadata-token-ttl-seconds": "21600"}
        )
        token_request.timeout = 1
        
        with urllib.request.urlopen(token_request, timeout=1) as response:
            token = response.read().decode('utf-8')
        
        headers = {"X-aws-ec2-metadata-token": token}
        
        # Get availability zone
        az_request = urllib.request.Request(
            "http://169.254.169.254/latest/meta-data/placement/availability-zone",
            headers=headers
        )
        with urllib.request.urlopen(az_request, timeout=1) as response:
            az = response.read().decode('utf-8')
            info["availability_zone"] = az
            # Region is AZ without the last character (e.g., us-east-1a -> us-east-1)
            info["region"] = az[:-1]
        
        # Get instance ID
        instance_request = urllib.request.Request(
            "http://169.254.169.254/latest/meta-data/instance-id",
            headers=headers
        )
        with urllib.request.urlopen(instance_request, timeout=1) as response:
            info["instance_id"] = response.read().decode('utf-8')
            
    except Exception:
        # Not on AWS EC2 or metadata not available
        # Check for AWS_DEFAULT_REGION or AWS_REGION environment variable
        info["region"] = os.environ.get("AWS_DEFAULT_REGION", 
                                        os.environ.get("AWS_REGION", "local"))
    
    return info


def is_base64_image(content: str) -> bool:
    """
    Check if the content is a base64 encoded image.
    
    Args:
        content: String to check
        
    Returns:
        True if content appears to be base64 image data
    """
    if not content or len(content) < 100:
        return False
    
    # Check if it starts with data URI scheme
    if content.startswith('data:image/'):
        return True
    
    # Check if it looks like raw base64 (no URL-like patterns)
    if content.startswith(('http://', 'https://', '/')):
        return False
    
    # Check for valid base64 characters
    base64_pattern = re.compile(r'^[A-Za-z0-9+/=]+$')
    
    # Sample first 1000 chars for efficiency
    sample = content[:1000].replace('\n', '').replace('\r', '').replace(' ', '')
    
    if not base64_pattern.match(sample):
        return False
    
    # Try to decode a small portion to verify
    try:
        # Base64 strings should have length divisible by 4
        test_len = min(100, len(sample))
        test_len = test_len - (test_len % 4)
        base64.b64decode(sample[:test_len])
        return True
    except Exception:
        return False


def get_report_subdir_name() -> str:
    """
    Generate report subdirectory name based on date, region and IP.
    
    Format: YYYYMMDD_region_ip
    Example: 20251224_cn-north-1_202.101.0.16
    
    Returns:
        Subdirectory name string
    """
    machine_info = get_machine_info()
    date_str = datetime.now().strftime("%Y%m%d")
    region = machine_info["region"].replace("_", "-")
    ip = machine_info["ip_address"].replace(".", ".")  # Keep dots for IP
    
    return f"{date_str}_{region}_{ip}"
