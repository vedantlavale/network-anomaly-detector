import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, 
                    filename='../data/detector_debug.log',
                    format='%(asctime)s - %(levelname)s - %(message)s')

def detect_anomalies(logs):
    """Detect anomalies in network logs"""
    logging.info(f"Processing {len(logs)} logs")
    
    # Debug first log structure
    if logs and len(logs) > 0:
        logging.info(f"First log entry keys: {list(logs[0].keys())}")
    
    # Convert logs to DataFrame
    df = pd.DataFrame(logs)
    
    # Basic validation
    if df.empty or len(df) < 5:
        logging.warning("Not enough logs for analysis")
        return []
    
    # Add basic anomalies regardless of statistical analysis
    basic_anomalies = []
    for log in logs:
        # Check for status codes
        status_code = log.get('status_code')
        if status_code:
            # Convert to int if it's a string
            if isinstance(status_code, str):
                try:
                    status_code = int(status_code)
                except ValueError:
                    continue
                    
            if 400 <= status_code < 500:
                # Add more detailed error classification
                error_type = "client_error"
                description = "Client error"
                
                if status_code == 400:
                    error_type = "bad_request"
                    description = "Bad request - malformed syntax"
                elif status_code == 401:
                    error_type = "unauthorized" 
                    description = "Authentication required"
                elif status_code == 403:
                    error_type = "forbidden"
                    description = "Access forbidden - authorization failed"
                elif status_code == 404:
                    error_type = "not_found" 
                    description = "Resource not found"
                elif status_code == 405:
                    error_type = "method_not_allowed"
                    description = "Method not allowed for this resource"
                elif status_code == 429:
                    error_type = "rate_limited"
                    description = "Too many requests - rate limit exceeded"
                
                basic_anomalies.append({
                    **log,
                    'anomaly_type': error_type,
                    'description': description,
                    'severity': 'medium'
                })
            elif 500 <= status_code < 600:
                # More specific server error types
                error_type = "server_error"
                description = f"Server error {status_code}"
                
                if status_code == 500:
                    description = "Internal server error"
                elif status_code == 502:
                    description = "Bad gateway"
                elif status_code == 503:
                    description = "Service unavailable"
                elif status_code == 504:
                    description = "Gateway timeout"
                
                basic_anomalies.append({
                    **log,
                    'anomaly_type': error_type,
                    'description': description,
                    'severity': 'medium'
                })
        
        # Check for slow responses
        duration = log.get('duration') or log.get('response_time')
        if duration and (isinstance(duration, (int, float)) and duration > 3000):  # Over 3s
            basic_anomalies.append({
                **log,
                'anomaly_type': 'slow_request',
                'timing': duration
            })
    
    if basic_anomalies:
        logging.info(f"Found {len(basic_anomalies)} basic anomalies before statistical analysis")
        return basic_anomalies
    
    # Continue with statistical analysis as before
    try:
        # Feature Engineering
        for required_col in ['timestamp', 'status_code', 'url']:
            if required_col not in df.columns:
                logging.error(f"Missing required column: {required_col}")
                return basic_anomalies
        
        # Convert timestamp
        try:
            df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
            df['hour'] = df['timestamp'].dt.hour
            df['minute'] = df['timestamp'].dt.minute
        except Exception as e:
            logging.error(f"Error processing timestamp: {e}")
            return basic_anomalies
        
        # Convert status_code
        try:
            df['status_code'] = pd.to_numeric(df['status_code'], errors='coerce')
        except Exception as e:
            logging.error(f"Error processing status_code: {e}")
            return basic_anomalies
        
        # Extract domain from URL
        df['domain'] = df['url'].apply(lambda x: extract_domain(x))
        
        # Calculate request frequency per domain and resource type
        df['domain_count'] = df.groupby('domain')['domain'].transform('count')
        df['resource_type_count'] = df.groupby('resource_type')['resource_type'].transform('count')
        
        # Calculate timing features if available
        if 'duration' in df.columns:
            df['log_duration'] = np.log1p(df['duration'])
        
        # Features for anomaly detection
        features = ['status_code', 'hour', 'minute', 'domain_count', 'resource_type_count']
        if 'log_duration' in df.columns:
            features.append('log_duration')
        
        # Normalize features
        scaler = StandardScaler()
        scaled_features = scaler.fit_transform(df[features])
        
        # Train Isolation Forest with optimized parameters
        model = IsolationForest(
            n_estimators=100,
            contamination=0.05,  # Adjusted based on expected anomaly rate
            max_samples='auto',
            random_state=42
        )
        
        # Predict anomalies
        df['anomaly_score'] = model.fit_predict(scaled_features)
        df['anomaly_confidence'] = model.score_samples(scaled_features)
        
        # Get anomalies (outliers have score -1)
        anomalies = df[df['anomaly_score'] == -1]
        
        # Classify anomaly types
        result = []
        for _, row in anomalies.iterrows():
            anomaly_info = row.to_dict()
            
            # Determine anomaly type
            if 400 <= row['status_code'] < 500:
                anomaly_info['anomaly_type'] = 'client_error'
            elif 500 <= row['status_code'] < 600:
                anomaly_info['anomaly_type'] = 'server_error'
            elif 'duration' in row and row['duration'] > 5000:  # Over 5s
                anomaly_info['anomaly_type'] = 'slow_request'
            else:
                anomaly_info['anomaly_type'] = 'statistical_outlier'
                
            result.append(anomaly_info)
            
        return result
    except Exception as e:
        logging.error(f"Error in statistical analysis: {e}")
        return basic_anomalies

def extract_domain(url):
    """Extract domain from URL"""
    try:
        from urllib.parse import urlparse
        parsed_url = urlparse(url)
        return parsed_url.netloc
    except:
        return url