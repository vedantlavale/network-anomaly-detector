import os
import uuid
import subprocess
import json
from datetime import datetime
from detector import detect_anomalies

def process_url_async(url, task_id=None):
    """Run analysis in a separate process"""
    if not task_id:
        task_id = str(uuid.uuid4())
    
    # Store task status
    tasks_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../data/tasks.json')
    task = {
        'id': task_id,
        'url': url,
        'status': 'running',
        'created_at': datetime.now().isoformat()
    }
    
    # Save task status
    tasks = []
    if os.path.exists(tasks_path):
        with open(tasks_path, 'r') as f:
            try:
                tasks = json.load(f)
            except json.JSONDecodeError:
                tasks = []
    
    tasks.append(task)
    with open(tasks_path, 'w') as f:
        json.dump(tasks, f, indent=2)
    
    # Start analysis process in background
    try:
        # Process logic here
        pass
    except Exception as e:
        # Update task status on error
        update_task_status(task_id, 'error', str(e))