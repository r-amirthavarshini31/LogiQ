"""
LogiQ Runbook Generator Module
Generates Markdown runbooks for anomalies via LLM or template fallback.
"""

import os
import json
import requests
from datetime import datetime

from database.db import get_setting


def generate_runbook_with_openai(anomaly):
    """
    Generate a runbook using OpenAI API.

    Args:
        anomaly (dict): Anomaly data including message, category, level, explanation, fix.

    Returns:
        str or None: Markdown runbook content, or None on failure.
    """
    api_key = os.getenv('OPENAI_API_KEY') or get_setting('openai_api_key')
    if not api_key:
        return None

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)

        prompt = f"""Generate a detailed Markdown runbook for resolving this server anomaly.

## Anomaly Details
- **Level**: {anomaly.get('level', 'error')}
- **Category**: {anomaly.get('category', 'Unknown')}
- **Message**: {anomaly.get('message', '')}
- **Explanation**: {anomaly.get('explanation', '')}
- **Suggested Fix**: {anomaly.get('suggested_fix', '')}

The runbook should include:
1. Overview/Summary
2. Impact Assessment
3. Prerequisites
4. Step-by-Step Resolution
5. Verification Steps
6. Rollback Plan
7. Prevention Measures

Use proper Markdown formatting with headers, code blocks, and numbered steps."""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a senior SRE writing operational runbooks. Be thorough, precise, and include specific commands."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=1500,
        )

        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"OpenAI runbook generation error: {e}")
        return None


def generate_runbook_with_ollama(anomaly):
    """
    Generate a runbook using local Ollama instance.

    Args:
        anomaly (dict): Anomaly data.

    Returns:
        str or None: Markdown runbook content, or None on failure.
    """
    endpoint = os.getenv('OLLAMA_ENDPOINT') or get_setting('ollama_endpoint') or 'http://localhost:11434'

    prompt = f"""Generate a Markdown runbook for resolving this anomaly:
Level: {anomaly.get('level', 'error')}
Category: {anomaly.get('category', 'Unknown')}
Message: {anomaly.get('message', '')}

Include: Overview, Impact, Steps, Verification, Rollback, Prevention."""

    try:
        response = requests.post(
            f"{endpoint}/api/generate",
            json={"model": "llama3.2", "prompt": prompt, "stream": False},
            timeout=60,
        )
        if response.status_code == 200:
            return response.json().get('response', '')
    except Exception as e:
        print(f"Ollama runbook generation error: {e}")
    return None


def generate_runbook_fallback(anomaly):
    """
    Generate a runbook using a template-based fallback.

    Args:
        anomaly (dict): Anomaly data.

    Returns:
        str: Markdown runbook content.
    """
    level = anomaly.get('level', 'error').upper()
    category = anomaly.get('category', 'Unknown')
    message = anomaly.get('message', 'No message available')
    explanation = anomaly.get('explanation', 'No explanation available')
    fix = anomaly.get('suggested_fix', 'No fix available')
    timestamp = anomaly.get('timestamp', datetime.now().isoformat())

    # Category-specific verification commands
    verification_commands = {
        'Database': '```bash\n# Check database connectivity\nmysql -u root -p -e "SELECT 1;"\n# or\npsql -U postgres -c "SELECT 1;"\n\n# Check connection pool status\nnetstat -an | grep 3306 | wc -l\n```',
        'Network': '```bash\n# Test connectivity\nping -c 4 <target-host>\ntraceroute <target-host>\ncurl -v https://<target-endpoint>\n\n# Check DNS\nnslookup <hostname>\ndig <hostname>\n```',
        'Auth': '```bash\n# Check authentication service status\nsystemctl status <auth-service>\n\n# Review recent auth failures\ngrep "auth\\|login\\|denied" /var/log/auth.log | tail -20\n\n# Verify token validity\ncurl -H "Authorization: Bearer <token>" <auth-endpoint>/verify\n```',
        'Memory': '```bash\n# Check current memory usage\nfree -h\ntop -b -n1 | head -20\n\n# Check for OOM kills\ndmesg | grep -i "out of memory"\njournalctl -k | grep -i oom\n\n# Process memory usage\nps aux --sort=-%mem | head -10\n```',
        'File System': '```bash\n# Check disk space\ndf -h\ndu -sh /* | sort -rh | head -10\n\n# Check for I/O errors\ndmesg | grep -i "i/o error"\n\n# Check file permissions\nls -la <path>\nstat <path>\n```',
        'Timeout': '```bash\n# Check service response time\ncurl -o /dev/null -s -w "%%{time_total}" <endpoint>\n\n# Check network latency\nping -c 10 <target>\n\n# Monitor service health\nwatch -n 1 "curl -s -o /dev/null -w \'%%{http_code}\' <health-endpoint>"\n```',
    }

    verify_block = verification_commands.get(category, '```bash\n# Check application logs\ntail -100 /var/log/<application>.log\n\n# Check system health\nuptime\nfree -h\ndf -h\n```')

    runbook = f"""# Runbook: {category} {level} Resolution

**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Severity**: {level}
**Category**: {category}
**Anomaly ID**: #{anomaly.get('id', 'N/A')}

---

## 1. Overview

{explanation}

**Original Log Entry:**
```
{message}
```

**Detected At:** {timestamp}

---

## 2. Impact Assessment

| Aspect | Assessment |
|--------|-----------|
| Severity | **{level}** |
| Category | {category} |
| User Impact | {'High — service may be degraded or unavailable' if level in ('CRITICAL', 'ERROR') else 'Medium — functionality may be partially affected'} |
| Urgency | {'Immediate action required' if level == 'CRITICAL' else 'Address within current shift' if level == 'ERROR' else 'Address during next maintenance window'} |

---

## 3. Prerequisites

- [ ] Access to the affected server/service
- [ ] Appropriate permissions (sudo/admin)
- [ ] Monitoring dashboard access
- [ ] Communication channel to stakeholders

---

## 4. Step-by-Step Resolution

{fix}

---

## 5. Verification

After applying the fix, verify the resolution:

{verify_block}

**Success Criteria:**
- [ ] No new occurrences of the error in logs
- [ ] Service health checks passing
- [ ] Response times within acceptable thresholds
- [ ] No related alerts firing

---

## 6. Rollback Plan

If the fix causes additional issues:

1. Revert any configuration changes made
2. Restart affected services to restore previous state
3. Document what went wrong for post-mortem
4. Escalate to the next support tier if needed

---

## 7. Prevention Measures

- Set up monitoring alerts for early detection
- Add automated health checks for the affected component
- Document this incident in the knowledge base
- Review and update capacity planning if resource-related
- Consider implementing circuit breakers for resilience

---

*Generated by LogiQ — From chaos to clarity, in seconds.*
"""

    return runbook


def generate_runbook(anomaly):
    """
    Generate a runbook for an anomaly using the best available method.

    Priority: OpenAI → Ollama → Template fallback

    Args:
        anomaly (dict): Anomaly data.

    Returns:
        str: Markdown runbook content.
    """
    # Try OpenAI
    runbook = generate_runbook_with_openai(anomaly)
    if runbook:
        return runbook

    # Try Ollama
    runbook = generate_runbook_with_ollama(anomaly)
    if runbook:
        return runbook

    # Fallback to template
    return generate_runbook_fallback(anomaly)
