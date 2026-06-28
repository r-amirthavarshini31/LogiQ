"""
LogiQ Log Parser Module
Handles parsing of various log file formats into structured entries.
Supports: syslog, Apache/Nginx, JSON-structured, and generic timestamped logs.
"""

import re
import json
from datetime import datetime

# Common log level patterns
LOG_LEVELS = {
    'FATAL': 'critical',
    'CRITICAL': 'critical',
    'CRIT': 'critical',
    'ERROR': 'error',
    'ERR': 'error',
    'WARNING': 'warning',
    'WARN': 'warning',
    'INFO': 'info',
    'DEBUG': 'debug',
    'TRACE': 'debug',
    'NOTICE': 'info',
    'ALERT': 'critical',
    'EMERGENCY': 'critical',
    'EMERG': 'critical',
}

# Regex patterns for timestamp extraction
TIMESTAMP_PATTERNS = [
    # ISO 8601: 2024-01-15T14:30:00.000Z or 2024-01-15 14:30:00,000
    (r'(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}[.,]?\d{0,6}\s*[Z+-]?\d{0,4})', '%Y-%m-%dT%H:%M:%S'),
    # Syslog: Jan 15 14:30:00
    (r'([A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})', '%b %d %H:%M:%S'),
    # Apache/Nginx: [15/Jan/2024:14:30:00 +0000]
    (r'\[(\d{2}/[A-Z][a-z]{2}/\d{4}:\d{2}:\d{2}:\d{2}\s*[+-]\d{4})\]', '%d/%b/%Y:%H:%M:%S %z'),
    # Unix timestamp
    (r'(\d{10,13})', 'unix'),
    # Simple date: 2024-01-15 14:30:00
    (r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})', '%Y-%m-%d %H:%M:%S'),
    # MM/DD/YYYY HH:MM:SS
    (r'(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}:\d{2})', '%m/%d/%Y %H:%M:%S'),
]

# Regex for log level extraction
LEVEL_PATTERN = re.compile(
    r'\b(' + '|'.join(LOG_LEVELS.keys()) + r')\b',
    re.IGNORECASE
)


def extract_timestamp(line):
    """
    Extract a timestamp from a log line.

    Args:
        line (str): A single line from a log file.

    Returns:
        str or None: ISO 8601 formatted timestamp string, or None if not found.
    """
    for pattern, fmt in TIMESTAMP_PATTERNS:
        match = re.search(pattern, line)
        if match:
            raw = match.group(1).strip()
            try:
                if fmt == 'unix':
                    ts = int(raw)
                    if ts > 1e12:
                        ts = ts / 1000
                    return datetime.fromtimestamp(ts).isoformat()
                else:
                    dt = datetime.strptime(raw.split('.')[0].split(',')[0].strip('Z'), fmt.split('.')[0])
                    if dt.year == 1900:
                        dt = dt.replace(year=datetime.now().year)
                    return dt.isoformat()
            except (ValueError, OSError):
                continue
    return None


def extract_level(line):
    """
    Extract the log level from a log line.

    Args:
        line (str): A single line from a log file.

    Returns:
        str: Normalized log level ('critical', 'error', 'warning', 'info', 'debug').
    """
    match = LEVEL_PATTERN.search(line)
    if match:
        return LOG_LEVELS.get(match.group(1).upper(), 'info')
    
    # Fallback: check for common error indicators
    lower = line.lower()
    if any(kw in lower for kw in ['exception', 'traceback', 'panic', 'fatal']):
        return 'error'
    if any(kw in lower for kw in ['fail', 'refused', 'denied', 'timeout']):
        return 'warning'
    return 'info'


def parse_json_line(line):
    """
    Attempt to parse a line as a JSON-structured log entry.

    Args:
        line (str): A single line from a log file.

    Returns:
        dict or None: Parsed entry dict, or None if not valid JSON log.
    """
    try:
        data = json.loads(line.strip())
        if isinstance(data, dict):
            message = (
                data.get('message') or data.get('msg') or 
                data.get('log') or data.get('text') or str(data)
            )
            level = data.get('level') or data.get('severity') or data.get('loglevel') or 'info'
            level_str = level if isinstance(level, str) else str(level)
            normalized_level = LOG_LEVELS.get(level_str.upper(), level_str.lower())
            
            timestamp = (
                data.get('timestamp') or data.get('time') or 
                data.get('@timestamp') or data.get('ts') or data.get('date')
            )
            
            return {
                'timestamp': str(timestamp) if timestamp else None,
                'level': normalized_level,
                'message': message,
            }
    except (json.JSONDecodeError, TypeError):
        pass
    return None


def parse_log_content(content):
    """
    Parse raw log file content into structured entries.

    Automatically detects the log format and parses accordingly.
    Supports JSON, syslog, Apache/Nginx, and generic text formats.

    Args:
        content (str): Raw content of the log file.

    Returns:
        list[dict]: List of parsed log entries, each containing:
            - line_number (int): 1-indexed line number
            - timestamp (str or None): ISO 8601 timestamp
            - level (str): Normalized log level
            - message (str): The log message content
            - raw_line (str): The original line text
    """
    lines = content.strip().split('\n')
    entries = []
    multiline_buffer = None

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue

        # Check if this is a continuation of a multi-line entry (e.g., stack trace)
        if multiline_buffer and not extract_timestamp(stripped) and not parse_json_line(stripped):
            multiline_buffer['message'] += '\n' + stripped
            multiline_buffer['raw_line'] += '\n' + line
            continue
        
        # Flush previous multi-line buffer
        if multiline_buffer:
            entries.append(multiline_buffer)
            multiline_buffer = None

        # Try JSON parsing first
        json_entry = parse_json_line(stripped)
        if json_entry:
            entry = {
                'line_number': i + 1,
                'timestamp': json_entry['timestamp'],
                'level': json_entry['level'],
                'message': json_entry['message'],
                'raw_line': line,
            }
        else:
            # Generic parsing
            timestamp = extract_timestamp(line)
            level = extract_level(line)
            
            # Extract the message (remove timestamp and level from the line)
            message = stripped
            for pattern, _ in TIMESTAMP_PATTERNS:
                message = re.sub(pattern, '', message, count=1)
            message = LEVEL_PATTERN.sub('', message, count=1)
            # Clean up separators and whitespace
            message = re.sub(r'^[\s\-\[\]:>|]+', '', message).strip()
            if not message:
                message = stripped

            entry = {
                'line_number': i + 1,
                'timestamp': timestamp,
                'level': level,
                'message': message,
                'raw_line': line,
            }

        # Check if this might start a multi-line entry
        if entry['level'] in ('error', 'critical'):
            multiline_buffer = entry
        else:
            entries.append(entry)

    # Flush final buffer
    if multiline_buffer:
        entries.append(multiline_buffer)

    return entries
