import os
import json
from google.cloud import firestore
from datetime import datetime
from flask import Response

# Initialize Firestore client
# Will use GOOGLE_CLOUD_PROJECT environment variable if set
db = firestore.Client()

def validate_auth(request):
    """
    Validate authentication for the request.
    Supports multiple methods:
    1. API Key (if API_KEY env var is set) - passed as 'apiKey' query param or 'X-API-Key' header
    2. Google Cloud IAM token (automatic if function requires IAM auth)
    
    Returns: (is_authorized, error_response)
    """
    api_key = os.environ.get('API_KEY')
    
    # If API key is configured, validate it
    if api_key:
        # Check query parameter first, then header
        provided_key = request.args.get('apiKey') or request.headers.get('X-API-Key')
        
        if not provided_key:
            return False, Response(
                json.dumps({
                    'status': 'error',
                    'message': 'Authentication required. Provide apiKey parameter or X-API-Key header.'
                }),
                status=401,
                mimetype='application/json'
            )
        
        if provided_key != api_key:
            return False, Response(
                json.dumps({
                    'status': 'error',
                    'message': 'Invalid API key'
                }),
                status=403,
                mimetype='application/json'
            )
    
    # If no API key is configured, rely on IAM authentication
    # (Cloud Functions will handle IAM auth automatically if configured)
    return True, None

def record_reading(request):
    """
    Cloud Function to record temperature or humidity readings to Firestore.
    
    Expected GET parameters:
    - measure: 'temperature' or 'humidity'
    - sensorID: unique identifier for the sensor
    - value: the measured value (float)
    - apiKey: API key for authentication (if API_KEY env var is set)
    
    Alternatively, use X-API-Key header for API key authentication.
    
    Returns:
    - JSON response with status and message
    """
    # Validate authentication
    is_authorized, auth_error = validate_auth(request)
    if not is_authorized:
        return auth_error
    
    # Get query parameters
    measure = request.args.get('measure')
    sensor_id = request.args.get('sensorID')
    value = request.args.get('value')
    
    # Validate required parameters
    if not measure:
        response_data = {
            'status': 'error',
            'message': 'Missing required parameter: measure'
        }
        return Response(
            json.dumps(response_data),
            status=400,
            mimetype='application/json'
        )
    
    if not sensor_id:
        response_data = {
            'status': 'error',
            'message': 'Missing required parameter: sensorID'
        }
        return Response(
            json.dumps(response_data),
            status=400,
            mimetype='application/json'
        )
    
    if not value:
        response_data = {
            'status': 'error',
            'message': 'Missing required parameter: value'
        }
        return Response(
            json.dumps(response_data),
            status=400,
            mimetype='application/json'
        )
    
    # Validate measure type
    if measure.lower() not in ['temperature', 'humidity']:
        response_data = {
            'status': 'error',
            'message': f"Invalid measure type: {measure}. Must be 'temperature' or 'humidity'"
        }
        return Response(
            json.dumps(response_data),
            status=400,
            mimetype='application/json'
        )
    
    # Validate and convert value to float
    try:
        value_float = float(value)
    except ValueError:
        response_data = {
            'status': 'error',
            'message': f'Invalid value format: {value}. Must be a number'
        }
        return Response(
            json.dumps(response_data),
            status=400,
            mimetype='application/json'
        )
    
    try:
        # Create document in Firestore
        # Collection structure: readings/{sensorID}_{timestamp}
        timestamp = datetime.now(datetime.UTC)
        doc_id = f"{sensor_id}_{timestamp.isoformat()}"
        
        doc_ref = db.collection('readings').document(doc_id)
        doc_ref.set({
            'measure': measure.lower(),
            'sensorID': sensor_id,
            'value': value_float,
            'timestamp': timestamp,
            'created_at': firestore.SERVER_TIMESTAMP
        })
        
        response_data = {
            'status': 'success',
            'message': 'Reading recorded successfully',
            'data': {
                'measure': measure.lower(),
                'sensorID': sensor_id,
                'value': value_float,
                'timestamp': timestamp.isoformat(),
                'document_id': doc_id
            }
        }
        return Response(
            json.dumps(response_data),
            status=200,
            mimetype='application/json'
        )
        
    except Exception as e:
        response_data = {
            'status': 'error',
            'message': f'Failed to record reading: {str(e)}'
        }
        return Response(
            json.dumps(response_data),
            status=500,
            mimetype='application/json'
        )


def get_last_temperature(request):
    """
    Cloud Function to return the last recorded temperature from Firestore.

    Optional GET parameters:
    - apiKey: API key for authentication (if API_KEY env var is set)

    Alternatively, use X-API-Key header for API key authentication.

    Returns:
    - JSON response with status and data (last reading or null)
    """
    # Validate authentication
    is_authorized, auth_error = validate_auth(request)
    if not is_authorized:
        return auth_error

    try:
        query = (
            db.collection('readings')
            .where('measure', '==', 'temperature')
            .order_by('timestamp', direction=firestore.Query.DESCENDING)
            .limit(1)
        )
        docs = list(query.stream())

        if not docs:
            response_data = {
                'status': 'success',
                'message': 'No temperature readings found',
                'data': None
            }
            return Response(
                json.dumps(response_data),
                status=200,
                mimetype='application/json'
            )

        doc = docs[0]
        data = doc.to_dict()
        timestamp = data.get('timestamp')
        if hasattr(timestamp, 'isoformat'):
            timestamp_str = timestamp.isoformat()
        else:
            timestamp_str = str(timestamp) if timestamp else None

        response_data = {
            'status': 'success',
            'message': 'Last temperature reading',
            'data': {
                'measure': data.get('measure'),
                'sensorID': data.get('sensorID'),
                'value': data.get('value'),
                'timestamp': timestamp_str,
                'document_id': doc.id
            }
        }
        return Response(
            json.dumps(response_data),
            status=200,
            mimetype='application/json'
        )

    except Exception as e:
        response_data = {
            'status': 'error',
            'message': f'Failed to get last temperature: {str(e)}'
        }
        return Response(
            json.dumps(response_data),
            status=500,
            mimetype='application/json'
        )
