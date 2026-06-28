"""
LogiQ Anomaly Detector Module
Identifies anomalies in parsed log entries using keyword matching and frequency spike detection.
"""

from collections import defaultdict
from datetime import datetime, timedelta

# Keywords that indicate anomalous log entries, with severity weights
ANOMALY_KEYWORDS = {
    'critical': {
        'keywords': [
            'fatal', 'panic', 'emergency', 'critical', 'catastrophic',
            'system failure', 'kernel panic', 'segfault', 'segmentation fault',
            'out of memory', 'oom', 'disk full', 'data corruption',
        ],
        'weight': 1.0,
    },
    'error': {
        'keywords': [
            'error', 'exception', 'traceback', 'failed', 'failure',
            'unable to', 'cannot', 'could not', 'refused', 'rejected',
            'denied', 'unauthorized', 'forbidden', 'not found',
            'null pointer', 'nullpointerexception', 'runtime error',
            'syntax error', 'type error', 'value error', 'key error',
            'connection reset', 'broken pipe', 'socket error',
        ],
        'weight': 0.8,
    },
    'warning': {
        'keywords': [
            'warning', 'warn', 'deprecated', 'timeout', 'timed out',
            'retry', 'retrying', 'slow query', 'high latency',
            'disk usage', 'memory usage', 'cpu usage',
            'rate limit', 'throttl', 'backoff',
            'certificate expir', 'ssl error',
        ],
        'weight': 0.5,
    },
}

# Minimum severity score to classify as anomaly
ANOMALY_THRESHOLD = 0.3

# Spike detection settings
SPIKE_WINDOW_SECONDS = 60
SPIKE_MULTIPLIER = 3.0


def calculate_severity_score(entry):
    """
    Calculate a severity score for a log entry based on keyword matching.

    Args:
        entry (dict): A parsed log entry with 'message' and 'level' keys.

    Returns:
        float: Severity score between 0.0 and 1.0.
    """
    message_lower = entry.get('message', '').lower()
    raw_lower = entry.get('raw_line', '').lower()
    text = message_lower + ' ' + raw_lower
    max_score = 0.0

    for level_name, config in ANOMALY_KEYWORDS.items():
        for keyword in config['keywords']:
            if keyword in text:
                max_score = max(max_score, config['weight'])

    # Boost score based on parsed log level
    level = entry.get('level', 'info')
    level_boost = {
        'critical': 0.3,
        'error': 0.2,
        'warning': 0.1,
        'info': 0.0,
        'debug': 0.0,
    }
    max_score = min(1.0, max_score + level_boost.get(level, 0.0))

    return max_score


def detect_frequency_spikes(entries):
    """
    Detect time windows with abnormally high error frequency.

    Groups entries into time windows and flags windows where the error count
    exceeds SPIKE_MULTIPLIER times the average.

    Args:
        entries (list[dict]): Parsed log entries with timestamps.

    Returns:
        set: Set of line numbers that fall within spike windows.
    """
    # Group entries by time window
    time_buckets = defaultdict(list)

    for entry in entries:
        ts_str = entry.get('timestamp')
        if not ts_str:
            continue
        try:
            ts = datetime.fromisoformat(ts_str.replace('Z', '+00:00').replace('+00:00', ''))
        except (ValueError, TypeError):
            continue

        # Round down to the nearest window
        bucket_key = ts.replace(
            second=(ts.second // SPIKE_WINDOW_SECONDS) * SPIKE_WINDOW_SECONDS if SPIKE_WINDOW_SECONDS <= 60 else 0,
            microsecond=0
        )
        time_buckets[bucket_key].append(entry)

    if not time_buckets:
        return set()

    # Calculate average and find spikes
    counts = [len(v) for v in time_buckets.values()]
    avg_count = sum(counts) / len(counts) if counts else 0
    threshold = max(avg_count * SPIKE_MULTIPLIER, 5)

    spike_lines = set()
    for bucket_key, bucket_entries in time_buckets.items():
        if len(bucket_entries) > threshold:
            for entry in bucket_entries:
                spike_lines.add(entry.get('line_number'))

    return spike_lines


def detect_anomalies(entries):
    """
    Run full anomaly detection on parsed log entries.

    Combines keyword-based severity scoring with frequency spike detection
    to identify anomalous log entries.

    Args:
        entries (list[dict]): Parsed log entries from the parser module.

    Returns:
        list[dict]: Anomalous entries with added 'severity_score' and 'is_spike' fields.
                    Only entries exceeding the anomaly threshold are returned.
    """
    spike_lines = detect_frequency_spikes(entries)
    anomalies = []

    for entry in entries:
        score = calculate_severity_score(entry)
        is_spike = entry.get('line_number') in spike_lines

        # Boost score for entries in spike windows
        if is_spike:
            score = min(1.0, score + 0.2)

        if score >= ANOMALY_THRESHOLD:
            entry['severity_score'] = round(score, 3)
            entry['is_spike'] = is_spike

            # Upgrade level based on score if needed
            if score >= 0.8 and entry.get('level') not in ('critical',):
                entry['level'] = 'error'
            elif score >= 0.9:
                entry['level'] = 'critical'

            anomalies.append(entry)

    # Sort by severity score descending
    anomalies.sort(key=lambda x: x.get('severity_score', 0), reverse=True)

    return anomalies
