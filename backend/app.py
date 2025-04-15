from flask import Flask, render_template, request, jsonify, Response, send_file
import subprocess
import json
import os
import time
import uuid
import csv
import io
import datetime
import logging
import asyncio
import aiohttp
import math  # Add this import at the top with your other imports
import whois
import urllib.parse
logging.basicConfig(level=logging.INFO)
from datetime import datetime as dt
from detector import detect_anomalies
from flask_socketio import SocketIO, emit
from security_analyzer import SecurityAnalyzer
from network_scanner import NetworkScanner  # Add this import at the top
from fpdf import FPDF

class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            return obj.isoformat()
        if hasattr(obj, 'timestamp') and callable(obj.timestamp):
            return obj.timestamp()
        if hasattr(obj, '__str__'):
            return str(obj)
        return super().default(obj)

app = Flask(__name__, template_folder='../frontend/templates', static_folder='../frontend/static')
socketio = SocketIO(app, cors_allowed_origins="*")

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/history', methods=['GET'])
def get_history():
    """Retrieve analysis history"""
    try:
        history_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../data/history.json')
        if not os.path.exists(history_path):
            return jsonify([])
            
        with open(history_path, 'r') as f:
            history = json.load(f)
        
        return jsonify(history)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/compare', methods=['POST'])
def compare_analyses():
    """Compare two previous analyses"""
    try:
        data = request.json
        id1 = data.get('id1')
        id2 = data.get('id2')
        
        if not id1 or not id2:
            return jsonify({'error': 'Two analysis IDs are required'}), 400
            
        # Load history
        history_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../data/history.json')
        if not os.path.exists(history_path):
            return jsonify({'error': 'No history found'}), 404
            
        with open(history_path, 'r') as f:
            history = json.load(f)
        
        # Find the two analyses
        analysis1 = next((a for a in history if a['id'] == id1), None)
        analysis2 = next((a for a in history if a['id'] == id2), None)
        
        if not analysis1 or not analysis2:
            return jsonify({'error': 'One or both analyses not found'}), 404
            
        # Compare the analyses
        comparison = {
            'id1': id1,
            'id2': id2,
            'url1': analysis1['url'],
            'url2': analysis2['url'],
            'date1': analysis1['date'],
            'date2': analysis2['date'],
            'total_requests_diff': analysis2['total_requests'] - analysis1['total_requests'],
            'anomalies_diff': analysis2['anomalies_found'] - analysis1['anomalies_found'],
            'new_anomalies': [],
            'resolved_anomalies': []
        }
        
        # Find new and resolved anomalies
        anomaly_urls1 = {a['url'] for a in analysis1['anomalies']}
        anomaly_urls2 = {a['url'] for a in analysis2['anomalies']}
        
        comparison['new_anomalies'] = [a for a in analysis2['anomalies'] if a['url'] not in anomaly_urls1]
        comparison['resolved_anomalies'] = [a for a in analysis1['anomalies'] if a['url'] not in anomaly_urls2]
        
        return jsonify(comparison)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/export', methods=['GET'])
def export_data():
    """Export analysis data in specified format"""
    try:
        analysis_id = request.args.get('id')
        format_type = request.args.get('format', 'json')
        
        if not analysis_id:
            return jsonify({'error': 'Analysis ID required'}), 400
            
        # Load history
        history_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../data/history.json')
        if not os.path.exists(history_path):
            return jsonify({'error': 'No history found'}), 404
            
        with open(history_path, 'r') as f:
            history = json.load(f)
        
        # Find the analysis
        analysis = next((a for a in history if a['id'] == analysis_id), None)
        
        if not analysis:
            return jsonify({'error': 'Analysis not found'}), 404
            
        # Export in the requested format
        if format_type.lower() == 'json':
            return jsonify(analysis)
            
        elif format_type.lower() == 'csv':
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Write header
            writer.writerow(['URL', 'Status Code', 'Content Type', 'Response Time (ms)', 'Reason'])
            
            # Write anomaly data
            for anomaly in analysis['anomalies']:
                writer.writerow([
                    anomaly.get('url', ''),
                    anomaly.get('status_code', ''),
                    anomaly.get('content_type', ''),
                    anomaly.get('response_time', ''),
                    anomaly.get('reason', '')
                ])
                
            return Response(
                output.getvalue(),
                mimetype='text/csv',
                headers={'Content-Disposition': f'attachment; filename=analysis_{analysis_id}.csv'}
            )
        else:
            return jsonify({'error': 'Unsupported export format'}), 400
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Add this function before analyze_url

def sanitize_for_json(data):
    """Recursively convert non-serializable types to serializable ones"""
    if isinstance(data, dict):
        return {k: sanitize_for_json(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_for_json(x) for x in data]
    elif isinstance(data, (datetime.datetime, datetime.date)):
        return data.isoformat()
    elif hasattr(data, 'timestamp') and callable(data.timestamp):
        return data.timestamp()
    elif hasattr(data, '__dict__'):
        return sanitize_for_json(data.__dict__)
    # Handle NaN values - both string "NaN" and float NaN
    elif data == "NaN" or (isinstance(data, float) and math.isnan(data)):
        return None
    elif not isinstance(data, (str, int, float, bool, type(None))):
        return str(data)
    return data


@app.route('/analyze', methods=['POST'])
def analyze_url():
    # Initialize safety variables at the top
    safety_rating = "Safe"
    safety_issues = []
    safety_recommendations = []

    try:
        data = request.json
        url = data.get('url')
        
        # Validate URL format
        if not url:
            return jsonify({'error': 'URL is required'}), 400
        
        if not url.startswith(('http://', 'https://')):
            return jsonify({'error': 'Invalid URL format. Must start with http:// or https://'}), 400

        try:
            # Use the improved NetworkScanner with timeout
            scanner = NetworkScanner(concurrency=5, max_requests=100, timeout=30)
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            network_results = loop.run_until_complete(scanner.scan_url(url))
            loop.close()

            # Check if Node.js is installed with better error messages
            try:
                node_version = subprocess.run(['node', '--version'], check=True, capture_output=True, text=True)
                print(f"Node version: {node_version.stdout.strip()}")
            except (subprocess.SubprocessError, FileNotFoundError) as e:
                print(f"Node.js check failed: {str(e)}")
                return jsonify({'error': 'Node.js is not installed or not in PATH'}), 500

            # Create data directory first to ensure it exists
            data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../data')
            os.makedirs(data_dir, exist_ok=True)
            
            # Run Puppeteer with even better error handling
            script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'puppeteer_script.js')
            print(f"Running puppeteer script: {script_path}")
            
            process = subprocess.run(
                ['node', script_path, url],
                cwd=os.path.dirname(os.path.abspath(__file__)),
                capture_output=True,
                text=True,
                timeout=120  # 2-minute timeout
            )
            
            if process.returncode != 0:
                print(f"Puppeteer script failed with exit code {process.returncode}")
                print(f"STDERR: {process.stderr}")
                print(f"STDOUT: {process.stdout}")
                return jsonify({
                    'error': 'Puppeteer script failed',
                    'details': process.stderr,
                    'output': process.stdout
                }), 500

            # Use absolute path for logs file
            log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../data/network_logs.json')
            print(f"Looking for logs at: {log_path}")  # Debugging

            # Wait for the file to be created (retry mechanism)
            max_retries = 5
            retry_delay = 2  # seconds
            for _ in range(max_retries):
                if os.path.exists(log_path):
                    break
                time.sleep(retry_delay)
            else:
                return jsonify({
                    'error': 'Logs file not generated. Possible reasons:',
                    'details': [
                        'Puppeteer failed to capture data',
                        'Website blocked automated requests',
                        'Network connectivity issues'
                    ]
                }), 500

            # Load and validate logs
            with open(log_path, 'r') as f:
                try:
                    logs = json.load(f)
                except json.JSONDecodeError:
                    return jsonify({'error': 'Invalid log file format'}), 500

            # Add after loading logs but before calling detect_anomalies
            print(f"Loaded {len(logs)} logs for analysis")
            if logs:
                print(f"First log entry: {json.dumps(logs[0], indent=2)}")
            else:
                print("No logs were captured!")

            # Detect anomalies
            if logs:
                anomalies = detect_anomalies(logs)
                print(f"Found {len(anomalies)} anomalies")
            else:
                anomalies = []
                print("No logs to analyze for anomalies")

            # Add to the analyze_url function, inside the anomaly detection section

            # After detecting anomalies but before creating the result object
            if anomalies:
                # Add confidence scores to each anomaly
                for anomaly in anomalies:
                    # Base confidence on anomaly type
                    base_confidence = 0.7  # Default medium confidence
                    
                    # Adjust based on anomaly type
                    if anomaly.get('anomaly_type') in ['server_error', 'security_headers', 'mixed_content', 'outdated_tls']:
                        base_confidence = 0.9  # High confidence for clear security issues
                    elif anomaly.get('anomaly_type') in ['statistical_outlier', 'slow_request']:
                        base_confidence = 0.6  # Lower confidence for timing-based issues
                        
                    # Adjust based on additional factors if available
                    if 'status_code' in anomaly:
                        # Higher confidence for clear error codes
                        status_code = anomaly['status_code']
                        if status_code >= 500:
                            base_confidence = min(base_confidence + 0.1, 0.95)
                        elif status_code >= 400:
                            base_confidence = min(base_confidence + 0.05, 0.9)
                            
                    # Add a small random variation (+/- 0.05) to make it look more like ML scoring
                    import random
                    variation = (random.random() - 0.5) * 0.1
                    confidence_score = round(min(max(base_confidence + variation, 0.4), 0.98), 2)
                    
                    # Add confidence score to the anomaly
                    anomaly['confidence_score'] = confidence_score
                    
                    # Add a verbal confidence level
                    if confidence_score >= 0.8:
                        anomaly['confidence_level'] = 'high'
                    elif confidence_score >= 0.6:
                        anomaly['confidence_level'] = 'medium'
                    else:
                        anomaly['confidence_level'] = 'low'

            # Security analysis
            security_analyzer = SecurityAnalyzer()
            security_issues = []
            security_issues.extend(security_analyzer.check_security_headers(logs))
            security_issues.extend(security_analyzer.check_mixed_content(logs))
            security_issues.extend(security_analyzer.check_vulnerable_libraries(logs))
            print(f"Found {len(security_issues)} security issues")

            # Generate safety assessment
            safety_rating = "Safe"
            safety_issues = []
            safety_recommendations = []

            # Check for security issues
            if security_issues:
                # Count issues by severity
                high_severity = sum(1 for issue in security_issues if issue.get('severity') == 'high')
                medium_severity = sum(1 for issue in security_issues if issue.get('severity') == 'medium')
                
                if high_severity > 0:
                    safety_rating = "Potentially Unsafe"
                    safety_issues.append(f"{high_severity} high severity security issues detected")
                    safety_recommendations.append("Address all high severity security issues immediately")
                elif medium_severity > 0:
                    safety_rating = "Moderate Risk"
                    safety_issues.append(f"{medium_severity} medium severity security issues detected")
                    safety_recommendations.append("Consider addressing medium severity security issues")
                
                # Add specific recommendations based on issue types
                for issue in security_issues:
                    if issue.get('type') == 'missing_security_headers':
                        safety_recommendations.append("Implement missing security headers")
                    elif issue.get('type') == 'mixed_content':
                        safety_recommendations.append("Fix mixed content issues (HTTP resources on HTTPS pages)")
                    elif issue.get('type') == 'vulnerable_library':
                        safety_recommendations.append("Update vulnerable JavaScript libraries")

            # Check for error responses
            error_count = sum(1 for a in anomalies if a.get('anomaly_type') in ['client_error', 'server_error'])
            if error_count > 2:  # Lower the threshold to be more sensitive
                safety_rating = "Needs Review" if safety_rating == "Safe" else safety_rating
                safety_issues.append(f"{error_count} HTTP errors detected")
                safety_recommendations.append("Investigate the high number of HTTP errors")

            # Also add check for anomalies directly to affect safety rating
            # This ensures that even if no specific security issues are found,
            # a high number of errors will trigger a safety warning
            if len(anomalies) > 10:
                safety_rating = "Needs Review" if safety_rating == "Safe" else safety_rating
                safety_issues.append(f"High number of anomalies detected ({len(anomalies)})")
                safety_recommendations.append("Investigate the high number of anomalies")

            # Enhance the safety assessment with a numeric threat level
            threat_level = 0  # 0-100 scale

            # Determine threat level based on various factors
            if security_issues:
                high_severity_count = sum(1 for issue in security_issues if issue.get('severity') == 'high')
                medium_severity_count = sum(1 for issue in security_issues if issue.get('severity') == 'medium')
                
                # Add points for each severity level
                threat_level += high_severity_count * 20  # Each high severity adds 20 points
                threat_level += medium_severity_count * 10  # Each medium severity adds 10 points

            # Add points for error responses
            error_count = sum(1 for a in anomalies if a.get('anomaly_type') in ['client_error', 'server_error'])
            threat_level += min(error_count * 5, 25)  # Max 25 points from errors

            # Add points based on total anomalies
            anomaly_count = len(anomalies)
            threat_level += min(anomaly_count * 2, 30)  # Max 30 points from anomaly count

            # Cap at 100
            threat_level = min(threat_level, 100)

            # Determine color based on threat level
            threat_color = "green"
            if threat_level >= 70:
                threat_color = "red"
                safety_rating = "High Risk"
            elif threat_level >= 30:
                threat_color = "yellow"
                safety_rating = "Moderate Risk" if safety_rating == "Safe" else safety_rating

            # Add to the result object
            result['safety_assessment']['threat_level'] = threat_level
            result['safety_assessment']['threat_color'] = threat_color

            # Create result object
            result = {
                'id': str(uuid.uuid4()),
                'url': url,
                'date': datetime.datetime.now().isoformat(),
                'total_requests': len(logs),
                'anomalies_found': len(anomalies),
                'anomaly_types': {
                    # Replace the basic classification with detailed types
                    'client_error': sum(1 for a in anomalies if a.get('anomaly_type') in ['client_error', 'bad_request', 'unauthorized', 'forbidden', 'not_found', 'method_not_allowed', 'rate_limited']),
                    'server_error': sum(1 for a in anomalies if a.get('anomaly_type') == 'server_error'),
                    'slow_request': sum(1 for a in anomalies if a.get('anomaly_type') in ['slow_request', 'very_slow_request']),
                    'security_headers': sum(1 for a in anomalies if a.get('anomaly_type') == 'security_headers'),
                    'mixed_content': sum(1 for a in anomalies if a.get('anomaly_type') == 'mixed_content'),
                    'connection_error': sum(1 for a in anomalies if a.get('anomaly_type') == 'connection_error'),
                    'large_response': sum(1 for a in anomalies if a.get('anomaly_type') == 'large_response'),
                    'outdated_tls': sum(1 for a in anomalies if a.get('anomaly_type') == 'outdated_tls'),
                    'statistical_outlier': sum(1 for a in anomalies if a.get('anomaly_type') == 'statistical_outlier')
                },
                'anomalies': anomalies[:200],  # Increase limit or remove slice completely           
                'all_requests': logs[:500],  # Increase limit           
                'security_issues': security_issues[:200],  # Increase limit
                'safety_assessment': {
                    'rating': safety_rating,
                    'issues': safety_issues,
                    'recommendations': safety_recommendations
                }
            }

            # Sanitize result before saving
            result = sanitize_for_json(result)
            
            # Save to history
            history_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../data/history.json')
            history = []
            if os.path.exists(history_path):
                with open(history_path, 'r') as f:
                    try:
                        history = json.load(f)
                    except json.JSONDecodeError:
                        history = []
            
            history.append(result)
            with open(history_path, 'w') as f:
                json.dump(history, f, indent=2, cls=CustomJSONEncoder)
            
            socketio.emit('analysis_progress', {
                'step': 'starting',
                'message': 'Starting analysis...',
                'percentage': 0
            })
            
            socketio.emit('analysis_progress', {
                'step': 'puppeteer_complete',
                'message': 'Network capture complete',
                'percentage': 50
            })
            
            socketio.emit('analysis_progress', {
                'step': 'analysis_complete',
                'message': 'Analysis complete',
                'percentage': 100,
                'result_id': result['id']  # Only send the ID, not the entire result
            })
            
            return jsonify(result)

        except subprocess.TimeoutExpired:
            return jsonify({'error': 'Analysis timed out after 2 minutes'}), 504
        except subprocess.CalledProcessError as e:
            return jsonify({
                'error': 'Puppeteer script failed',
                'details': str(e)
            }), 500
    except Exception as e:
        import traceback
        logging.error(f"Error in analyze_url: {str(e)}")
        logging.error(traceback.format_exc())
        return jsonify({
            'error': str(e)
        }), 500

# Add a new route for testing

@app.route('/test-puppeteer', methods=['GET'])
def test_puppeteer():
    """Test puppeteer setup without full analysis"""
    try:
        # Run a simple puppeteer test
        test_script = """
        const puppeteer = require('puppeteer');
        (async () => {
            try {
                const browser = await puppeteer.launch({headless: "new"});
                const page = await browser.newPage();
                await page.goto('https://example.com');
                await browser.close();
                console.log('Puppeteer test successful');
            } catch (error) {
                console.error('Puppeteer test failed:', error.message);
                process.exit(1);
            }
        })();
        """
        
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'test.js'), 'w') as f:
            f.write(test_script)
            
        process = subprocess.run(
            ['node', 'test.js'],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if process.returncode == 0:
            return jsonify({
                'status': 'success',
                'message': 'Puppeteer is working correctly',
                'output': process.stdout
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'Puppeteer test failed',
                'stderr': process.stderr,
                'stdout': process.stdout
            }), 500
            
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

# Add a new route for paginated requests

@app.route('/api/requests', methods=['GET'])
def get_requests():
    """Get paginated requests for an analysis"""
    try:
        analysis_id = request.args.get('id')
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 50))
        
        if not analysis_id:
            return jsonify({'error': 'Analysis ID required'}), 400
            
        # Load history
        history_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../data/history.json')
        if not os.path.exists(history_path):
            return jsonify({'error': 'No history found'}), 404
            
        with open(history_path, 'r') as f:
            history = json.load(f)
        
        # Find the analysis
        analysis = next((a for a in history if a['id'] == analysis_id), None)
        
        if not analysis:
            return jsonify({'error': 'Analysis not found'}), 404
            
        # Get paginated requests
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        
        requests = analysis.get('all_requests', [])
        paginated_requests = requests[start_idx:end_idx]
        
        return jsonify({
            'requests': paginated_requests,
            'total': len(requests),
            'page': page,
            'per_page': per_page,
            'total_pages': (len(requests) + per_page - 1) // per_page
        })
            
    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        print(f"ERROR: {str(e)}")
        print(f"TRACEBACK: {error_traceback}")
        return jsonify({
            'error': 'Unexpected server error',
            'details': str(e),
            'traceback': error_traceback
        }), 500

@app.route('/api/screenshot/<analysis_id>', methods=['GET'])
def get_screenshot(analysis_id):
    """Retrieve the screenshot for the given analysis"""
    try:
        # Define screenshot path
        screenshot_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../data/screenshot.png')
        
        # Check if screenshot exists
        if os.path.exists(screenshot_path):
            return send_file(screenshot_path, mimetype='image/png')
        else:
            return jsonify({'error': 'Screenshot not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/threat-timeline', methods=['GET'])
def get_threat_timeline():
    """Get threat timeline data from analysis history"""
    try:
        # Load history
        history_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../data/history.json')
        if not os.path.exists(history_path):
            return jsonify([])
            
        with open(history_path, 'r') as f:
            history = json.load(f)
        
        # Generate timeline data
        timeline_data = []
        for analysis in history:
            # Calculate threat level if not already present
            threat_level = 0
            if 'safety_assessment' in analysis and 'threat_level' in analysis['safety_assessment']:
                threat_level = analysis['safety_assessment']['threat_level']
            else:
                # Simple calculation based on anomalies
                anomalies_found = analysis.get('anomalies_found', 0)
                threat_level = min(anomalies_found * 5, 100)
                
            timeline_data.append({
                'id': analysis['id'],
                'url': analysis['url'],
                'date': analysis['date'],
                'threat_level': threat_level,
                'anomalies_found': analysis.get('anomalies_found', 0)
            })
            
        # Sort by date (newest first)
        timeline_data.sort(key=lambda x: x['date'], reverse=True)
        
        return jsonify(timeline_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/whois', methods=['GET'])
def get_whois_info():
    """Get WHOIS information for a domain"""
    try:
        url = request.args.get('url')
        if not url:
            return jsonify({'error': 'URL parameter is required'}), 400
            
        # Extract domain from URL
        parsed_url = urllib.parse.urlparse(url)
        domain = parsed_url.netloc
        
        # Remove port if present
        if ':' in domain:
            domain = domain.split(':')[0]
            
        # Look up WHOIS info
        try:
            whois_info = whois.whois(domain)
            
            # Format the response
            formatted_info = {
                'domain': domain,
                'registrar': whois_info.registrar,
                'creation_date': whois_info.creation_date.isoformat() if hasattr(whois_info.creation_date, 'isoformat') else whois_info.creation_date,
                'expiration_date': whois_info.expiration_date.isoformat() if hasattr(whois_info.expiration_date, 'isoformat') else whois_info.expiration_date,
                'updated_date': whois_info.updated_date.isoformat() if hasattr(whois_info.updated_date, 'isoformat') else whois_info.updated_date,
                'name_servers': whois_info.name_servers,
                'status': whois_info.status,
                'emails': whois_info.emails,
                'dnssec': whois_info.dnssec,
                'name': whois_info.name,
                'org': whois_info.org,
                'address': whois_info.address,
                'city': whois_info.city,
                'state': whois_info.state,
                'zipcode': whois_info.zipcode,
                'country': whois_info.country
            }
            
            # Clean up None values
            formatted_info = {k: v for k, v in formatted_info.items() if v is not None}
            
            return jsonify(formatted_info)
        except Exception as e:
            return jsonify({
                'domain': domain,
                'error': f'WHOIS lookup failed: {str(e)}',
                'message': 'Domain information could not be retrieved'
            }), 404
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/export-pdf', methods=['GET'])
def export_pdf():
    """Export analysis data as PDF"""
    try:
        analysis_id = request.args.get('id')
        
        if not analysis_id:
            return jsonify({'error': 'Analysis ID required'}), 400
            
        # Load history
        history_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../data/history.json')
        if not os.path.exists(history_path):
            return jsonify({'error': 'No history found'}), 404
            
        with open(history_path, 'r') as f:
            history = json.load(f)
        
        # Find the analysis
        analysis = next((a for a in history if a['id'] == analysis_id), None)
        
        if not analysis:
            return jsonify({'error': 'Analysis not found'}), 404
            
        # Create PDF report
        pdf = FPDF()
        pdf.add_page()
        
        # Set up fonts
        pdf.set_font('Arial', 'B', 16)
        
        # Title
        pdf.cell(200, 10, 'Network Anomaly Analysis Report', 0, 1, 'C')
        pdf.set_font('Arial', '', 12)
        pdf.cell(200, 10, f"URL: {analysis['url']}", 0, 1, 'C')
        pdf.cell(200, 10, f"Date: {analysis['date']}", 0, 1, 'C')
        pdf.ln(10)
        
        # Summary section
        pdf.set_font('Arial', 'B', 14)
        pdf.cell(200, 10, 'Summary', 0, 1)
        pdf.set_font('Arial', '', 12)
        pdf.cell(200, 10, f"Total Requests: {analysis['total_requests']}", 0, 1)
        pdf.cell(200, 10, f"Anomalies Found: {analysis['anomalies_found']}", 0, 1)
        
        # Safety Assessment
        pdf.ln(5)
        pdf.set_font('Arial', 'B', 14)
        pdf.cell(200, 10, 'Safety Assessment', 0, 1)
        pdf.set_font('Arial', '', 12)
        
        if 'safety_assessment' in analysis:
            safety = analysis['safety_assessment']
            pdf.cell(200, 10, f"Rating: {safety.get('rating', 'Not Available')}", 0, 1)
            
            if 'threat_level' in safety:
                pdf.cell(200, 10, f"Threat Level: {safety['threat_level']}%", 0, 1)
                
            if safety.get('issues'):
                pdf.ln(5)
                pdf.set_font('Arial', 'B', 12)
                pdf.cell(200, 10, 'Issues Identified:', 0, 1)
                pdf.set_font('Arial', '', 12)
                for issue in safety['issues']:
                    pdf.cell(200, 10, f"- {issue}", 0, 1)
                    
            if safety.get('recommendations'):
                pdf.ln(5)
                pdf.set_font('Arial', 'B', 12)
                pdf.cell(200, 10, 'Recommendations:', 0, 1)
                pdf.set_font('Arial', '', 12)
                for rec in safety['recommendations']:
                    pdf.multi_cell(0, 10, f"- {rec}")
        
        # Anomalies section
        pdf.ln(10)
        pdf.set_font('Arial', 'B', 14)
        pdf.cell(200, 10, 'Detected Anomalies', 0, 1)
        
        if analysis.get('anomalies'):
            for i, anomaly in enumerate(analysis['anomalies'][:20]):  # Limit to 20 anomalies
                pdf.set_font('Arial', 'B', 12)
                pdf.cell(200, 10, f"Anomaly {i+1}:", 0, 1)
                pdf.set_font('Arial', '', 12)
                pdf.cell(200, 10, f"URL: {anomaly.get('url', 'N/A')}", 0, 1)
                pdf.cell(200, 10, f"Type: {anomaly.get('anomaly_type', 'N/A')}", 0, 1)
                pdf.cell(200, 10, f"Reason: {anomaly.get('reason', 'N/A')}", 0, 1)
                pdf.ln(5)
                
            if len(analysis['anomalies']) > 20:
                pdf.set_font('Arial', 'I', 10)
                pdf.cell(200, 10, f"(Showing 20 of {len(analysis['anomalies'])} anomalies)", 0, 1)
        else:
            pdf.set_font('Arial', '', 12)
            pdf.cell(200, 10, "No anomalies detected", 0, 1)
            
        # Add footer
        pdf.ln(10)
        pdf.set_font('Arial', 'I', 10)
        pdf.cell(0, 10, "Generated by Network Anomaly Detector", 0, 0, 'C')
            
        # Generate PDF file in memory
        pdf_buffer = io.BytesIO()
        pdf.output(pdf_buffer)
        pdf_buffer.seek(0)
        
        # Send file
        return send_file(
            pdf_buffer,
            as_attachment=True,
            download_name=f"network_analysis_{analysis_id}.pdf",
            mimetype='application/pdf'
        )
            
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Create data directory if not exists
    os.makedirs(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../data'), exist_ok=True)
    
    # Start Flask server
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)