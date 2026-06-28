"""
LogiQ Anomaly Explainer Module
Generates AI-powered explanations for log anomalies.
Supports OpenAI, Ollama (local), and a rule-based fallback.
Always checks SQLite cache before making API calls.
"""

import hashlib
import os
import json
import requests

from database.db import check_explanation_cache, store_explanation_cache, get_setting

# Fallback explanations for common error patterns
FALLBACK_EXPLANATIONS = {
    'connection refused': {
        'explanation': 'The application attempted to connect to a service that is not listening on the expected port. This typically means the target service (database, API server, cache) is either not running, has crashed, or is listening on a different port/interface.',
        'fix': '1. Check if the target service is running: `systemctl status <service>` or `docker ps`\n2. Verify the port configuration matches: `netstat -tlnp | grep <port>`\n3. Check firewall rules: `iptables -L` or check security group settings\n4. Review the service logs for crash information\n5. Restart the service if needed: `systemctl restart <service>`',
    },
    'out of memory': {
        'explanation': 'The system or process ran out of available memory (RAM). This can happen when a process allocates too much memory due to a memory leak, processing very large datasets, or simply not having enough RAM provisioned for the workload.',
        'fix': '1. Identify the memory-hungry process: `top -o %MEM` or `ps aux --sort=-%mem`\n2. Check for memory leaks in application code (use profiling tools)\n3. Increase available memory or add swap space: `fallocate -l 2G /swapfile`\n4. Set memory limits for the process: use cgroups or container memory limits\n5. Optimize the application to use streaming/chunked processing for large datasets',
    },
    'timeout': {
        'explanation': 'An operation exceeded its maximum allowed execution time. This commonly occurs with database queries, API calls, or network requests when the target system is overloaded, the network is slow, or the operation is inherently too complex.',
        'fix': '1. Check the health of the target service/endpoint\n2. Review and optimize slow database queries: add indexes, simplify joins\n3. Increase timeout limits if the operation legitimately needs more time\n4. Implement retry logic with exponential backoff\n5. Consider adding a circuit breaker pattern to prevent cascade failures\n6. Monitor network latency between services',
    },
    'permission denied': {
        'explanation': 'The process attempted to access a resource (file, directory, port, or system call) without sufficient permissions. This usually indicates incorrect file ownership, restrictive permission bits, or SELinux/AppArmor policy violations.',
        'fix': '1. Check file permissions: `ls -la <path>`\n2. Verify the process is running as the correct user: `whoami` in the app context\n3. Fix ownership: `chown <user>:<group> <path>`\n4. Adjust permissions: `chmod 644 <file>` or `chmod 755 <directory>`\n5. Check SELinux: `getenforce` and review audit logs: `ausearch -m AVC`\n6. For port binding issues (< 1024), use setcap or run behind a reverse proxy',
    },
    'disk full': {
        'explanation': 'The filesystem has no remaining free space. This prevents the application from writing logs, temporary files, database records, or any other data. It can cause cascading failures across many services.',
        'fix': '1. Check disk usage: `df -h` and `du -sh /*`\n2. Find and remove large unnecessary files: `find / -size +100M -type f`\n3. Clear old log files: `journalctl --vacuum-size=500M`\n4. Empty trash and temporary directories\n5. Set up log rotation: configure logrotate\n6. Consider expanding the volume or adding additional storage\n7. Set up disk usage monitoring alerts before hitting 90%',
    },
    'null pointer': {
        'explanation': 'The application attempted to access or dereference a null/None reference. This is a programming error where code assumes an object exists when it may not — commonly from uninitialized variables, missing return values, or unexpected API responses.',
        'fix': '1. Review the stack trace to identify the exact line of code\n2. Add null checks before accessing the object: `if obj is not None`\n3. Use Optional types and proper error handling\n4. Validate API responses and database query results before accessing fields\n5. Add defensive programming: default values, guard clauses\n6. Write unit tests covering edge cases (empty inputs, missing data)',
    },
    'authentication': {
        'explanation': 'An authentication attempt failed. This could be due to invalid credentials, expired tokens, misconfigured authentication providers, or account lockout policies. It may also indicate a security breach attempt.',
        'fix': '1. Verify the credentials are correct and not expired\n2. Check if the account is locked: review auth provider dashboard\n3. Rotate and update API keys/tokens if expired\n4. Verify OAuth/JWT configuration: check issuer, audience, and signing keys\n5. Review authentication logs for brute force patterns\n6. Implement rate limiting on login endpoints\n7. Enable multi-factor authentication for sensitive accounts',
    },
    'database': {
        'explanation': 'A database operation failed. This could be due to connection issues, query syntax errors, constraint violations, deadlocks, or the database server being overloaded or unreachable.',
        'fix': '1. Check database server status and connectivity\n2. Review the specific error code and message\n3. For connection issues: check connection pool settings and limits\n4. For deadlocks: review transaction isolation levels and query order\n5. For constraint violations: validate data before inserting\n6. Optimize slow queries with EXPLAIN ANALYZE\n7. Monitor database performance metrics (connections, queries/sec, replication lag)',
    },
    'ssl': {
        'explanation': 'An SSL/TLS error occurred during a secure connection attempt. This typically indicates certificate issues — expired certificates, self-signed certificates not in the trust store, hostname mismatches, or protocol version incompatibilities.',
        'fix': '1. Check certificate expiration: `openssl s_client -connect host:port`\n2. Verify the certificate chain is complete\n3. Update the CA certificate bundle\n4. For self-signed certs in development: add to trust store or disable verification (dev only!)\n5. Ensure TLS version compatibility: prefer TLS 1.2+\n6. Renew certificates before expiration with automated tools like Let\'s Encrypt/certbot',
    },
}


def get_message_hash(message):
    """
    Generate a SHA-256 hash of a normalized error message for cache lookups.

    Args:
        message (str): The error message to hash.

    Returns:
        str: Hex digest of the SHA-256 hash.
    """
    normalized = message.strip().lower()
    # Remove timestamps, numbers, and UUIDs for better cache hit rates
    import re
    normalized = re.sub(r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}', '', normalized)
    normalized = re.sub(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', '', normalized)
    normalized = re.sub(r'\b\d+\b', 'N', normalized)
    normalized = re.sub(r'\s+', ' ', normalized).strip()

    return hashlib.sha256(normalized.encode()).hexdigest()


def explain_with_openai(message, category, level):
    """
    Get an explanation from OpenAI API.

    Args:
        message (str): The anomalous log message.
        category (str): Anomaly category.
        level (str): Severity level.

    Returns:
        dict: {'explanation': str, 'fix': str} or None on failure.
    """
    api_key = os.getenv('OPENAI_API_KEY') or get_setting('openai_api_key')
    if not api_key:
        return None

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        
        prompt = f"""Analyze this server log anomaly and provide:
1. A clear, concise explanation of what went wrong and why (2-3 sentences)
2. A step-by-step fix with specific commands where applicable

Log Entry:
Level: {level}
Category: {category}
Message: {message}

Respond in JSON format:
{{"explanation": "...", "fix": "..."}}"""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a senior DevOps engineer analyzing server log anomalies. Provide precise, actionable explanations and fixes."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=500,
        )

        content = response.choices[0].message.content.strip()
        # Try to parse JSON response
        if content.startswith('{'):
            return json.loads(content)
        elif '```json' in content:
            json_str = content.split('```json')[1].split('```')[0].strip()
            return json.loads(json_str)
        else:
            return {'explanation': content, 'fix': 'Review the explanation above for remediation steps.'}
    except Exception as e:
        print(f"OpenAI API error: {e}")
        return None


def explain_with_ollama(message, category, level):
    """
    Get an explanation from a local Ollama instance.

    Args:
        message (str): The anomalous log message.
        category (str): Anomaly category.
        level (str): Severity level.

    Returns:
        dict: {'explanation': str, 'fix': str} or None on failure.
    """
    endpoint = os.getenv('OLLAMA_ENDPOINT') or get_setting('ollama_endpoint') or 'http://localhost:11434'

    prompt = f"""Analyze this server log anomaly and provide a JSON response with 'explanation' and 'fix' keys.

Level: {level}
Category: {category}
Message: {message}

Respond ONLY with valid JSON: {{"explanation": "...", "fix": "..."}}"""

    try:
        response = requests.post(
            f"{endpoint}/api/generate",
            json={
                "model": "llama3.2",
                "prompt": prompt,
                "stream": False,
                "format": "json",
            },
            timeout=30,
        )
        if response.status_code == 200:
            result = response.json().get('response', '')
            return json.loads(result)
    except Exception as e:
        print(f"Ollama API error: {e}")
    return None


def explain_with_fallback(message, category, level):
    """
    Generate an explanation using rule-based pattern matching.

    This is the fallback when no LLM API is configured. It matches the error
    message against known patterns and returns pre-written explanations.

    Args:
        message (str): The anomalous log message.
        category (str): Anomaly category.
        level (str): Severity level.

    Returns:
        dict: {'explanation': str, 'fix': str}
    """
    message_lower = message.lower()

    # Check against known patterns
    for pattern, response in FALLBACK_EXPLANATIONS.items():
        if pattern in message_lower:
            return {'explanation': response['explanation'], 'fix': response['fix']}

    # Category-based fallback
    category_fallbacks = {
        'Database': {
            'explanation': f'A database-related {level} was detected. The operation involving the database layer failed or produced unexpected behavior. This could be related to connectivity, query execution, or data integrity issues.',
            'fix': '1. Check database server status and connectivity\n2. Review the specific error message for SQL-level details\n3. Check connection pool utilization\n4. Review recent schema changes or migrations\n5. Examine database performance metrics',
        },
        'Network': {
            'explanation': f'A network-related {level} occurred. Communication between services or with external endpoints failed. This may indicate network infrastructure issues, DNS problems, or service outages.',
            'fix': '1. Verify network connectivity: `ping` and `traceroute` to the target\n2. Check DNS resolution: `nslookup` or `dig`\n3. Review firewall and security group rules\n4. Check for network interface errors: `ifconfig` or `ip link`\n5. Monitor network traffic for anomalies',
        },
        'Auth': {
            'explanation': f'An authentication or authorization {level} was logged. Access control mechanisms rejected a request, which could indicate invalid credentials, insufficient permissions, or a potential security incident.',
            'fix': '1. Verify credentials and tokens are valid and current\n2. Check user/role permissions in the auth system\n3. Review recent changes to access policies\n4. Monitor for repeated failures (possible brute force)\n5. Audit authentication logs for suspicious patterns',
        },
        'Memory': {
            'explanation': f'A memory-related {level} was detected. The application or system is experiencing memory pressure, which can lead to performance degradation, crashes, or data loss.',
            'fix': '1. Monitor memory usage: `free -h` and `top`\n2. Profile the application for memory leaks\n3. Review recent code changes that may increase memory usage\n4. Adjust JVM heap size or process memory limits\n5. Consider vertical scaling or optimizing memory usage patterns',
        },
        'File System': {
            'explanation': f'A file system {level} occurred. Operations on files or directories failed, possibly due to permission issues, missing paths, disk space, or I/O errors.',
            'fix': '1. Check disk space: `df -h`\n2. Verify file/directory permissions and ownership\n3. Check for I/O errors in system logs: `dmesg | grep -i error`\n4. Ensure required paths exist and are accessible\n5. Monitor disk health: `smartctl -a /dev/sda`',
        },
        'Timeout': {
            'explanation': f'A timeout {level} was detected. An operation took longer than the configured maximum wait time. This commonly affects database queries, API calls, and inter-service communication.',
            'fix': '1. Identify the slow operation from the log context\n2. Check the target service health and response times\n3. Review and optimize the operation (query, API call)\n4. Consider increasing timeout values if the operation is legitimately slow\n5. Implement circuit breaker patterns for resilience',
        },
    }

    fallback = category_fallbacks.get(category, {
        'explanation': f'A {level}-level anomaly was detected in the application logs. The specific error pattern indicates an operational issue that requires investigation. Review the full log context and surrounding entries for additional clues.',
        'fix': '1. Review the complete log entry and surrounding context\n2. Check application and system health metrics\n3. Review recent deployments or configuration changes\n4. Search the error message in your knowledge base or issue tracker\n5. Escalate to the relevant team if the issue persists',
    })

    return fallback


def explain_anomaly(anomaly):
    """
    Generate an explanation for an anomaly, checking cache first.

    The lookup priority is:
    1. SQLite explanation cache (fastest, free)
    2. OpenAI API (if key configured)
    3. Ollama local LLM (if endpoint configured)
    4. Rule-based fallback (always available)

    Args:
        anomaly (dict): Anomaly data with 'message', 'category', and 'level' keys.

    Returns:
        dict: {'explanation': str, 'fix': str, 'cache_hit': bool}
    """
    message = anomaly.get('message', '')
    category = anomaly.get('category', 'Unknown')
    level = anomaly.get('level', 'error')

    # Step 1: Check cache
    msg_hash = get_message_hash(message)
    cached = check_explanation_cache(msg_hash)
    if cached:
        return {
            'explanation': cached['explanation'],
            'fix': cached['suggested_fix'],
            'cache_hit': True,
        }

    # Step 2: Try OpenAI
    result = explain_with_openai(message, category, level)

    # Step 3: Try Ollama
    if not result:
        result = explain_with_ollama(message, category, level)

    # Step 4: Fallback
    if not result:
        result = explain_with_fallback(message, category, level)

    # Cache the result
    explanation = result.get('explanation', '')
    fix = result.get('fix', '')
    store_explanation_cache(msg_hash, explanation, fix)

    return {
        'explanation': explanation,
        'fix': fix,
        'cache_hit': False,
    }
