FILE_TIMESTAMP_FORMAT = "%Y-%m-%dT%H-%M-%S-%fZ"
FILE_NAME_TEMPLATE = "{stem}_{timestamp}{suffix}"
FILE_SUFFIX = ".txt"
PRIVATE_KEY_STEM = "license_private_key"
LICENSE_STEM = "license"

RELATIVE_PREFIX = "+"
RELATIVE_PATTERN = r"^\+(\d+)([mhd])$"
RELATIVE_UNIT_SECONDS = {"m": 60, "h": 3600, "d": 86400}
RELATIVE_EXAMPLE = "+30d"
ABSOLUTE_EXAMPLE = "2027-01-01T00:00Z"
