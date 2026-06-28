"""
LogiQ — Log File Anomaly Explainer with Self-Healing Layer
Main Flask application entry point.

Routes:
    Page Routes:
        GET  /                  — Landing page
        GET  /dashboard         — Dashboard with anomaly analysis
        GET  /upload            — File upload page
        GET  /history           — Historical anomalies
        GET  /settings          — Application settings

    API Routes:
        POST   /api/upload              — Upload and analyze log file
        POST   /api/explain             — Get AI explanation for an anomaly
        POST   /api/runbook             — Generate runbook for an anomaly
        POST   /api/alert               — Send alert notification
        POST   /api/pr                  — Create GitHub pull request
        GET    /api/history             — Retrieve anomaly history
        PATCH  /api/anomaly/<id>/resolve — Mark anomaly as resolved
        GET    /api/settings            — Get current settings
        POST   /api/settings            — Save settings
        GET    /api/session/<id>        — Get session data with anomalies
        GET    /api/latest-session      — Get latest session data
"""

import os
import uuid
import json
from flask import Flask, request, jsonify, render_template, redirect, url_for
from flask_cors import CORS
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__,
            static_folder='static',
            template_folder='templates')
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'logiq-dev-secret')

# Enable CORS for local development
CORS(app)

# Initialize database
from database.db import (
    init_db, create_session, update_session_stats,
    insert_anomalies_batch, get_anomalies_by_session,
    get_anomaly_by_id, get_all_anomalies, update_anomaly_explanation,
    update_anomaly_runbook, resolve_anomaly, get_session,
    get_latest_session, get_all_settings, save_setting,
    get_lifetime_stats, get_all_sessions, delete_session_and_anomalies
)
from modules.parser import parse_log_content
from modules.detector import detect_anomalies
from modules.categorizer import categorize_anomalies
from modules.explainer import explain_anomaly
from modules.runbook import generate_runbook
from modules.alerting import send_alert
from modules.github_pr import create_fix_pr

init_db()


# ─── Page Routes ─────────────────────────────────────────────────────────────

@app.route('/')
def index():
    """Render the landing page."""
    return render_template('index.html')


@app.route('/dashboard')
def dashboard():
    """Render the dashboard page."""
    return render_template('dashboard.html')


@app.route('/upload')
def upload_page():
    """Render the upload page."""
    return render_template('upload.html')


@app.route('/history')
def history_page():
    """Render the history page."""
    return render_template('history.html')


@app.route('/settings')
def settings_page():
    """Render the settings page."""
    return render_template('settings.html')


@app.route('/login')
def login_page():
    """Render the login page."""
    return render_template('login.html')


@app.route('/signup')
def signup_page():
    """Render the signup page."""
    return render_template('signup.html')


@app.route('/profile')
def profile_page():
    """Render the user profile page."""
    return render_template('profile.html')


@app.route('/about')
def about_page():
    """Render the about page."""
    return render_template('about.html')


@app.route('/docs')
def docs_page():
    """Render the documentation page."""
    return render_template('docs.html')


# ─── API Routes ──────────────────────────────────────────────────────────────

@app.route('/api/upload', methods=['POST'])
def api_upload():
    """
    Upload and analyze a log file.

    Accepts multipart form data with a 'file' field.
    Parses the file, detects anomalies, categorizes them,
    and stores results in SQLite.

    Returns:
        JSON: {session_id, total_lines, anomaly_count, critical_count, anomalies}
    """
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    # Validate file extension
    allowed_extensions = {'.log', '.txt', '.csv'}
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed_extensions:
        return jsonify({'error': f'Unsupported file format. Allowed: {", ".join(allowed_extensions)}'}), 400

    try:
        # Read file content
        content = file.read().decode('utf-8', errors='replace')

        # Generate session ID
        session_id = str(uuid.uuid4())

        # Parse log entries
        entries = parse_log_content(content)
        total_lines = len(content.strip().split('\n'))

        # Detect anomalies
        anomalies = detect_anomalies(entries)

        # Categorize anomalies
        anomalies = categorize_anomalies(anomalies)

        # Create session record
        create_session(session_id, file.filename, total_lines)

        # Add session_id to each anomaly and store in database
        for anomaly in anomalies:
            anomaly['session_id'] = session_id

        anomaly_ids = insert_anomalies_batch(anomalies)

        # Assign database IDs back to anomalies
        for i, anomaly in enumerate(anomalies):
            anomaly['id'] = anomaly_ids[i]

        # Count critical anomalies
        critical_count = sum(1 for a in anomalies if a.get('level') == 'critical')

        # Update session stats
        update_session_stats(session_id, len(anomalies), critical_count)

        return jsonify({
            'session_id': session_id,
            'filename': file.filename,
            'total_lines': total_lines,
            'anomaly_count': len(anomalies),
            'critical_count': critical_count,
            'anomalies': anomalies,
        })

    except Exception as e:
        return jsonify({'error': f'Failed to process file: {str(e)}'}), 500


@app.route('/api/explain', methods=['POST'])
def api_explain():
    """
    Get an AI explanation for a single anomaly.

    Checks SQLite cache first, then calls LLM if no cache hit.

    Request Body:
        {anomaly_id: int} or {message: str, category: str, level: str}

    Returns:
        JSON: {explanation, fix, cache_hit}
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    anomaly_id = data.get('anomaly_id')

    if anomaly_id:
        anomaly = get_anomaly_by_id(anomaly_id)
        if not anomaly:
            return jsonify({'error': 'Anomaly not found'}), 404
    else:
        anomaly = {
            'message': data.get('message', ''),
            'category': data.get('category', 'Unknown'),
            'level': data.get('level', 'error'),
        }

    try:
        result = explain_anomaly(anomaly)

        # Update the database record if we have an ID
        if anomaly_id:
            update_anomaly_explanation(
                anomaly_id,
                result['explanation'],
                result['fix'],
                result['cache_hit']
            )

        return jsonify(result)

    except Exception as e:
        return jsonify({'error': f'Failed to generate explanation: {str(e)}'}), 500


@app.route('/api/runbook', methods=['POST'])
def api_runbook():
    """
    Generate a Markdown runbook for an anomaly.

    Request Body:
        {anomaly_id: int}

    Returns:
        JSON: {runbook: str (Markdown content)}
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    anomaly_id = data.get('anomaly_id')
    if not anomaly_id:
        return jsonify({'error': 'anomaly_id is required'}), 400

    anomaly = get_anomaly_by_id(anomaly_id)
    if not anomaly:
        return jsonify({'error': 'Anomaly not found'}), 404

    try:
        runbook_content = generate_runbook(anomaly)
        update_anomaly_runbook(anomaly_id, runbook_content)

        return jsonify({'runbook': runbook_content})

    except Exception as e:
        return jsonify({'error': f'Failed to generate runbook: {str(e)}'}), 500


@app.route('/api/alert', methods=['POST'])
def api_alert():
    """
    Send alert notifications to configured channels.

    Request Body:
        {anomaly_id: int}

    Returns:
        JSON: {success: bool, results: list}
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    anomaly_id = data.get('anomaly_id')
    if not anomaly_id:
        return jsonify({'error': 'anomaly_id is required'}), 400

    anomaly = get_anomaly_by_id(anomaly_id)
    if not anomaly:
        return jsonify({'error': 'Anomaly not found'}), 404

    try:
        result = send_alert(anomaly)
        return jsonify(result)

    except Exception as e:
        return jsonify({'error': f'Failed to send alert: {str(e)}'}), 500


@app.route('/api/pr', methods=['POST'])
def api_pr():
    """
    Create a GitHub pull request with a drafted patch.

    Request Body:
        {anomaly_id: int}

    Returns:
        JSON: {success: bool, message: str, pr_url: str}
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    anomaly_id = data.get('anomaly_id')
    if not anomaly_id:
        return jsonify({'error': 'anomaly_id is required'}), 400

    anomaly = get_anomaly_by_id(anomaly_id)
    if not anomaly:
        return jsonify({'error': 'Anomaly not found'}), 404

    try:
        result = create_fix_pr(anomaly)
        return jsonify(result)

    except Exception as e:
        return jsonify({'error': f'Failed to create PR: {str(e)}'}), 500


@app.route('/api/history', methods=['GET'])
def api_history():
    """
    Retrieve anomaly history with optional filters.

    Query Parameters:
        date_from, date_to, level, category, status

    Returns:
        JSON: {anomalies: list}
    """
    filters = {}
    for key in ('date_from', 'date_to', 'level', 'category', 'status'):
        val = request.args.get(key)
        if val:
            filters[key] = val

    anomalies = get_all_anomalies(filters if filters else None)
    return jsonify({'anomalies': anomalies})


@app.route('/api/anomaly/<int:anomaly_id>/resolve', methods=['PATCH'])
def api_resolve(anomaly_id):
    """
    Mark an anomaly as resolved.

    Returns:
        JSON: {success: bool, message: str}
    """
    anomaly = get_anomaly_by_id(anomaly_id)
    if not anomaly:
        return jsonify({'error': 'Anomaly not found'}), 404

    try:
        resolve_anomaly(anomaly_id)
        return jsonify({'success': True, 'message': 'Anomaly marked as resolved'})

    except Exception as e:
        return jsonify({'error': f'Failed to resolve anomaly: {str(e)}'}), 500


@app.route('/api/session/<session_id>', methods=['GET'])
def api_session(session_id):
    """
    Get session data with all its anomalies.

    Returns:
        JSON: {session: dict, anomalies: list}
    """
    session = get_session(session_id)
    if not session:
        return jsonify({'error': 'Session not found'}), 404

    anomalies = get_anomalies_by_session(session_id)
    return jsonify({'session': session, 'anomalies': anomalies})


@app.route('/api/latest-session', methods=['GET'])
def api_latest_session():
    """
    Get the most recent session data with anomalies.

    Returns:
        JSON: {session: dict, anomalies: list}
    """
    session = get_latest_session()
    if not session:
        return jsonify({'session': None, 'anomalies': []})

    anomalies = get_anomalies_by_session(session['id'])
    return jsonify({'session': session, 'anomalies': anomalies})


@app.route('/api/settings', methods=['GET'])
def api_get_settings():
    """
    Get all application settings.

    Returns:
        JSON: {settings: dict}
    """
    settings = get_all_settings()
    # Mask sensitive values
    masked = {}
    sensitive_keys = {'openai_api_key', 'github_token', 'twilio_auth_token'}
    for key, value in settings.items():
        if key in sensitive_keys and value:
            masked[key] = value[:8] + '••••••••'
        else:
            masked[key] = value
    return jsonify({'settings': masked})


@app.route('/api/settings', methods=['POST'])
def api_save_settings():
    """
    Save application settings.

    Request Body:
        {key: value, ...}

    Returns:
        JSON: {success: bool, message: str}
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    try:
        for key, value in data.items():
            # Don't save masked values
            if '••••••••' not in str(value):
                save_setting(key, str(value))

        return jsonify({'success': True, 'message': 'Settings saved successfully'})

    except Exception as e:
        return jsonify({'error': f'Failed to save settings: {str(e)}'}), 500


@app.route('/api/upload-preloaded', methods=['POST'])
def api_upload_preloaded():
    """
    Load a preloaded sample log file.
    
    Accepts JSON body with a 'dataset' key (e_commerce_outage, security_audit, kubernetes_cluster).
    Reads the file from static/preloaded, runs parse, detect, categorize,
    stores results in SQLite, and returns session ID and anomaly stats.
    """
    data = request.get_json()
    if not data or 'dataset' not in data:
        return jsonify({'error': 'No dataset selected'}), 400
        
    dataset = data['dataset']
    allowed_datasets = {
        'e_commerce_outage': 'static/preloaded/e_commerce_outage.log',
        'security_audit': 'static/preloaded/security_audit.log',
        'kubernetes_cluster': 'static/preloaded/kubernetes_cluster.log'
    }
    
    if dataset not in allowed_datasets:
        return jsonify({'error': 'Invalid dataset selected'}), 400
        
    filepath = allowed_datasets[dataset]
    filename = f"{dataset.replace('_', ' ').title()}.log"
    
    try:
        # Read preloaded file content
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
            
        # Generate session ID
        session_id = str(uuid.uuid4())

        # Parse log entries
        entries = parse_log_content(content)
        total_lines = len(content.strip().split('\n'))

        # Detect anomalies
        anomalies = detect_anomalies(entries)

        # Categorize anomalies
        anomalies = categorize_anomalies(anomalies)

        # Create session record
        create_session(session_id, filename, total_lines)

        # Add session_id to each anomaly and store in database
        for anomaly in anomalies:
            anomaly['session_id'] = session_id

        anomaly_ids = insert_anomalies_batch(anomalies)

        # Assign database IDs back to anomalies
        for i, anomaly in enumerate(anomalies):
            anomaly['id'] = anomaly_ids[i]

        # Count critical anomalies
        critical_count = sum(1 for a in anomalies if a.get('level') == 'critical')

        # Update session stats
        update_session_stats(session_id, len(anomalies), critical_count)

        return jsonify({
            'session_id': session_id,
            'filename': filename,
            'total_lines': total_lines,
            'anomaly_count': len(anomalies),
            'critical_count': critical_count,
            'anomalies': anomalies,
        })
        
    except Exception as e:
        return jsonify({'error': f'Failed to process preloaded dataset: {str(e)}'}), 500


@app.route('/api/profile/stats', methods=['GET'])
def api_profile_stats():
    """Get aggregated lifetime monitoring statistics."""
    try:
        stats = get_lifetime_stats()
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': f'Failed to fetch lifetime stats: {str(e)}'}), 500


@app.route('/api/profile/sessions', methods=['GET'])
def api_profile_sessions():
    """Retrieve all history sessions."""
    try:
        sessions = get_all_sessions()
        return jsonify({'sessions': sessions})
    except Exception as e:
        return jsonify({'error': f'Failed to fetch sessions list: {str(e)}'}), 500


@app.route('/api/session/<session_id>', methods=['DELETE'])
def api_delete_session(session_id):
    """Delete a session and all its associated anomalies."""
    try:
        # Check if session exists
        session = get_session(session_id)
        if not session:
            return jsonify({'error': 'Session not found'}), 404
            
        delete_session_and_anomalies(session_id)
        return jsonify({'success': True, 'message': 'Session deleted successfully'})
    except Exception as e:
        return jsonify({'error': f'Failed to delete session: {str(e)}'}), 500


@app.route('/api/history', methods=['DELETE'])
def api_clear_all_history():
    """Clear all sessions and anomalies from the database."""
    try:
        from database.db import clear_all_history
        clear_all_history()
        return jsonify({'success': True, 'message': 'History cleared successfully'})
    except Exception as e:
        return jsonify({'error': f'Failed to clear history: {str(e)}'}), 500


# ─── Main ────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print("\n  +======================================+")
    print("  |         LogiQ is running!            |")
    print("  |   From chaos to clarity - in seconds |")
    print("  |                                      |")
    print("  |   -> http://localhost:5000            |")
    print("  +======================================+\n")
    app.run(debug=True, host='0.0.0.0', port=5000)
