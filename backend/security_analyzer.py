class SecurityAnalyzer:
    """Analyzes network traffic for security issues"""
    
    def analyze_security(self, logs):
        """Perform security analysis on network logs"""
        security_issues = []
        
        # Check for missing security headers
        security_issues.extend(self.check_security_headers(logs))
        
        # Check for mixed content
        security_issues.extend(self.check_mixed_content(logs))
        
        # Check for vulnerable libraries
        security_issues.extend(self.check_vulnerable_libraries(logs))
        
        return security_issues
        
    def check_security_headers(self, logs):
        """Check for missing security headers in responses"""
        issues = []
        main_page_logs = [log for log in logs if log.get('resource_type') == 'document']
        
        for log in main_page_logs:
            headers = log.get('headers', {})
            missing_headers = []
            
            # Check for important security headers
            if not headers.get('content-security-policy'):
                missing_headers.append('Content-Security-Policy')
            
            if not headers.get('x-xss-protection'):
                missing_headers.append('X-XSS-Protection')
                
            if not headers.get('x-content-type-options'):
                missing_headers.append('X-Content-Type-Options')
                
            if not headers.get('strict-transport-security'):
                missing_headers.append('Strict-Transport-Security')
                
            if missing_headers:
                issues.append({
                    'type': 'missing_security_headers',
                    'url': log.get('url'),
                    'missing_headers': missing_headers,
                    'severity': 'medium',
                    'description': f"Missing important security headers: {', '.join(missing_headers)}"
                })
                
        return issues
        
    def check_mixed_content(self, logs):
        """Check for mixed content (HTTP resources on HTTPS pages)"""
        issues = []
        https_pages = [log for log in logs if log.get('url', '').startswith('https://') and log.get('resource_type') == 'document']
        
        for page in https_pages:
            page_url = page.get('url')
            http_resources = [log for log in logs 
                            if log.get('url', '').startswith('http://') and 
                            not log.get('url', '').startswith('https://')]
            
            if http_resources:
                issues.append({
                    'type': 'mixed_content',
                    'url': page_url,
                    'http_resources': [res.get('url') for res in http_resources[:5]],  # First 5 examples
                    'count': len(http_resources),
                    'severity': 'high',
                    'description': f"Found {len(http_resources)} HTTP resources on an HTTPS page"
                })
                
        return issues
        
    def check_vulnerable_libraries(self, logs):
        """Check for known vulnerable JavaScript libraries"""
        # This would require a database of vulnerable libraries and their signatures
        # Simplified placeholder implementation
        issues = []
        js_files = [log for log in logs if log.get('resource_type') == 'script']
        
        vulnerable_patterns = [
            {'pattern': 'jquery-1.', 'name': 'jQuery 1.x', 'severity': 'medium'},
            {'pattern': 'jquery-2.0.', 'name': 'jQuery 2.0.x', 'severity': 'medium'},
            {'pattern': 'angular-1.0.', 'name': 'AngularJS 1.0.x', 'severity': 'high'},
        ]
        
        for js in js_files:
            url = js.get('url', '')
            for vuln in vulnerable_patterns:
                if vuln['pattern'] in url:
                    issues.append({
                        'type': 'vulnerable_library',
                        'url': url,
                        'library': vuln['name'],
                        'severity': vuln['severity'],
                        'description': f"Potentially vulnerable library: {vuln['name']}"
                    })
                    
        return issues