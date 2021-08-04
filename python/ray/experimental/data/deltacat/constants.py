from ray.experimental.data.deltacat.utils.common import env_string

# Environment variables
DELTACAT_LOG_LEVEL = env_string(
    "DELTACAT_LOG_LEVEL",
    "DEBUG"
)
APPLICATION_LOG_LEVEL = env_string(
    "APPLICATION_LOG_LEVEL",
    "DEBUG"
)
JAVA_GATEWAY_AUTH_TOKEN = env_string(
    "JAVA_GATEWAY_AUTH_TOKEN",
    "f6346691-d8fc-48ae-8661-b7853de9917d"
)

# Byte Units
BYTES_PER_KIBIBYTE = 2**10
BYTES_PER_MEBIBYTE = 2**20
BYTES_PER_GIBIBYTE = 2**30
BYTES_PER_TEBIBYTE = 2**40
BYTES_PER_PEBIBYTE = 2**50
