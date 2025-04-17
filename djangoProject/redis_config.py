"""
Redis configuration settings for the Django project.
"""

# Base Redis configuration
REDIS_CONFIG = {
    "default": {
        "host": "127.0.0.1",
        "port": 6379,
        "db": 1,
        "socket_timeout": 5,
        "socket_connect_timeout": 5,
        "retry_on_timeout": True,
        "max_connections": 1000,
        "compressor": "django_redis.compressors.zlib.ZlibCompressor",
    }
}

# Cache configurations
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": f"redis://{REDIS_CONFIG['default']['host']}:{REDIS_CONFIG['default']['port']}/{REDIS_CONFIG['default']['db']}",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "SOCKET_CONNECT_TIMEOUT": REDIS_CONFIG['default']['socket_connect_timeout'],
            "SOCKET_TIMEOUT": REDIS_CONFIG['default']['socket_timeout'],
            "RETRY_ON_TIMEOUT": REDIS_CONFIG['default']['retry_on_timeout'],
            "MAX_CONNECTIONS": REDIS_CONFIG['default']['max_connections'],
            "COMPRESSOR": REDIS_CONFIG['default']['compressor'],
        }
    },
    "search_results": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": f"redis://{REDIS_CONFIG['default']['host']}:{REDIS_CONFIG['default']['port']}/2",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "SOCKET_CONNECT_TIMEOUT": REDIS_CONFIG['default']['socket_connect_timeout'],
            "SOCKET_TIMEOUT": REDIS_CONFIG['default']['socket_timeout'],
            "RETRY_ON_TIMEOUT": REDIS_CONFIG['default']['retry_on_timeout'],
            "MAX_CONNECTIONS": REDIS_CONFIG['default']['max_connections'],
            "COMPRESSOR": REDIS_CONFIG['default']['compressor'],
        }
    },
    "search_suggestions": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": f"redis://{REDIS_CONFIG['default']['host']}:{REDIS_CONFIG['default']['port']}/3",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "SOCKET_CONNECT_TIMEOUT": REDIS_CONFIG['default']['socket_connect_timeout'],
            "SOCKET_TIMEOUT": REDIS_CONFIG['default']['socket_timeout'],
            "RETRY_ON_TIMEOUT": REDIS_CONFIG['default']['retry_on_timeout'],
            "MAX_CONNECTIONS": REDIS_CONFIG['default']['max_connections'],
            "COMPRESSOR": REDIS_CONFIG['default']['compressor'],
        }
    },
    "term_expansion": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": f"redis://{REDIS_CONFIG['default']['host']}:{REDIS_CONFIG['default']['port']}/4",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "SOCKET_CONNECT_TIMEOUT": REDIS_CONFIG['default']['socket_connect_timeout'],
            "SOCKET_TIMEOUT": REDIS_CONFIG['default']['socket_timeout'],
            "RETRY_ON_TIMEOUT": REDIS_CONFIG['default']['retry_on_timeout'],
            "MAX_CONNECTIONS": REDIS_CONFIG['default']['max_connections'],
            "COMPRESSOR": REDIS_CONFIG['default']['compressor'],
        }
    }
}

# Cache time to live 
CACHE_TTL = 60 * 15  # 15 minutes 