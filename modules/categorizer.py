"""
LogiQ Anomaly Categorizer Module
Categorizes detected anomalies into predefined categories based on message content.
Categories: Database, Network, Auth, Memory, File System, Timeout, Application, Unknown.
"""

# Category definitions with keyword patterns
CATEGORIES = {
    'Database': {
        'keywords': [
            'sql', 'query', 'database', 'db ', 'mysql', 'postgres', 'postgresql',
            'sqlite', 'mongodb', 'redis', 'connection pool', 'deadlock',
            'table', 'column', 'index', 'transaction', 'rollback', 'commit',
            'foreign key', 'primary key', 'constraint', 'migration',
            'sequelize', 'sqlalchemy', 'prisma', 'orm', 'jdbc', 'odbc',
        ],
        'icon': 'database',
    },
    'Network': {
        'keywords': [
            'network', 'socket', 'tcp', 'udp', 'http', 'https', 'dns',
            'connection refused', 'connection reset', 'broken pipe',
            'econnrefused', 'econnreset', 'etimedout', 'enotfound',
            'host unreachable', 'no route', 'port', 'proxy',
            'ssl', 'tls', 'certificate', 'handshake',
            'curl', 'fetch', 'request', 'response', 'status code',
            'bandwidth', 'latency', 'packet', 'firewall',
        ],
        'icon': 'wifi',
    },
    'Auth': {
        'keywords': [
            'auth', 'authentication', 'authorization', 'login', 'logout',
            'password', 'credential', 'token', 'jwt', 'oauth', 'saml',
            'permission', 'forbidden', 'unauthorized', 'denied', 'access',
            '401', '403', 'rbac', 'role', 'session expired',
            'invalid token', 'expired token', 'api key', 'secret',
        ],
        'icon': 'lock',
    },
    'Memory': {
        'keywords': [
            'memory', 'ram', 'heap', 'stack', 'oom', 'out of memory',
            'memory leak', 'gc', 'garbage collect', 'allocation',
            'buffer overflow', 'segfault', 'segmentation fault',
            'core dump', 'null pointer', 'nullptr', 'dereference',
            'swap', 'virtual memory', 'resident', 'rss',
        ],
        'icon': 'cpu',
    },
    'File System': {
        'keywords': [
            'file', 'disk', 'storage', 'directory', 'folder', 'path',
            'read', 'write', 'permission denied', 'no such file',
            'disk full', 'disk space', 'inode', 'mount', 'unmount',
            'filesystem', 'io error', 'i/o error', 'enoent', 'eacces',
            'symlink', 'hardlink', 'truncat', 'corrupt',
        ],
        'icon': 'hard-drive',
    },
    'Timeout': {
        'keywords': [
            'timeout', 'timed out', 'deadline exceeded', 'ttl expired',
            'slow', 'latency', 'response time', 'hung', 'hanging',
            'unresponsive', 'not responding', 'heartbeat', 'keepalive',
            'circuit breaker', 'retry', 'backoff', 'rate limit',
            'throttl', 'queue full', 'overload',
        ],
        'icon': 'clock',
    },
    'Application': {
        'keywords': [
            'exception', 'traceback', 'error', 'bug', 'crash',
            'assertion', 'assert', 'runtime', 'syntax', 'type error',
            'value error', 'key error', 'attribute error', 'import error',
            'module not found', 'class not found', 'method not found',
            'undefined', 'nan', 'infinity', 'overflow', 'underflow',
            'deprecated', 'version', 'compatibility', 'config',
        ],
        'icon': 'code',
    },
}


def categorize_anomaly(entry):
    """
    Categorize a single anomaly based on its message content.

    Uses keyword matching against predefined category patterns.
    Returns the category with the highest keyword match count.

    Args:
        entry (dict): An anomaly entry with 'message' and 'raw_line' keys.

    Returns:
        str: Category name (e.g., 'Database', 'Network', 'Auth', etc.)
    """
    text = (entry.get('message', '') + ' ' + entry.get('raw_line', '')).lower()
    scores = {}

    for category, config in CATEGORIES.items():
        count = sum(1 for kw in config['keywords'] if kw in text)
        if count > 0:
            scores[category] = count

    if scores:
        return max(scores, key=scores.get)

    return 'Unknown'


def categorize_anomalies(anomalies):
    """
    Categorize a list of anomalies.

    Args:
        anomalies (list[dict]): List of anomaly entries.

    Returns:
        list[dict]: The same list with 'category' field added to each entry.
    """
    for anomaly in anomalies:
        anomaly['category'] = categorize_anomaly(anomaly)
    return anomalies


def get_category_icon(category):
    """
    Get the Lucide icon name for a category.

    Args:
        category (str): Category name.

    Returns:
        str: Lucide icon name.
    """
    config = CATEGORIES.get(category)
    return config['icon'] if config else 'help-circle'


def get_category_stats(anomalies):
    """
    Calculate category distribution statistics.

    Args:
        anomalies (list[dict]): List of categorized anomalies.

    Returns:
        dict: Category name to count mapping.
    """
    stats = {}
    for anomaly in anomalies:
        cat = anomaly.get('category', 'Unknown')
        stats[cat] = stats.get(cat, 0) + 1
    return stats
