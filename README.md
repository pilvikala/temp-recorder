# Temperature & Humidity Recorder

A Google Cloud Function that records temperature and humidity sensor readings to Firestore, deployed using Pulumi Infrastructure as Code.

## Features

- HTTP-triggered Cloud Function (GET requests)
- Stores sensor readings in Firestore
- Validates input parameters
- **Multiple authentication options** (API Key or Google Cloud IAM)
- Infrastructure as Code with Pulumi
- Environment-based configuration

## Prerequisites

1. **Google Cloud Account** with a project created
2. **Pulumi CLI** installed ([Installation Guide](https://www.pulumi.com/docs/get-started/install/))
3. **Google Cloud SDK** installed and configured
4. **Python 3.11+** installed
5. **Pulumi GCP plugin** installed

## Setup

### 1. Install Dependencies

```bash
# Install Python dependencies for Pulumi
pip install -r requirements.txt

# Install Pulumi GCP plugin (if not already installed)
pulumi plugin install resource gcp
```

### 2. Configure Pulumi

Set your Google Cloud project ID:

```bash
pulumi config set gcp:project YOUR_PROJECT_ID
pulumi config set projectId YOUR_PROJECT_ID
```

Optionally set the region (defaults to `us-central1`):

```bash
pulumi config set region us-west1
```

Optionally set a custom Firestore connection string:

```bash
pulumi config set firestoreConnection your-connection-string
```

### 2a. Configure Authentication

Choose one of the following authentication methods:

#### Option A: API Key Authentication (Recommended for IoT sensors)

Set an API key that will be required for all requests:

```bash
pulumi config set --secret apiKey your-secret-api-key-here
```

The `--secret` flag ensures the API key is encrypted in Pulumi's state.

#### Option B: Google Cloud IAM Authentication (Recommended for production)

No additional configuration needed. The function will require Google Cloud IAM authentication. You'll need to grant access to specific service accounts or users (see Authentication section below).

### 3. Enable Required APIs

Enable the necessary Google Cloud APIs:

```bash
gcloud services enable cloudfunctions.googleapis.com
gcloud services enable cloudbuild.googleapis.com
gcloud services enable firestore.googleapis.com
gcloud services enable storage.googleapis.com
```

### 4. Authenticate with Google Cloud

```bash
gcloud auth login
gcloud auth application-default login
```

## Deployment

### Deploy the Infrastructure

```bash
pulumi up
```

This will:
- Create a storage bucket for function source code
- Package and upload the Cloud Function
- Deploy the function with proper IAM permissions
- Output the function URL

### Get the Function URL

After deployment, the function URL will be displayed in the output. You can also retrieve it with:

```bash
pulumi stack output function_url
```

## Authentication

The function supports two authentication methods:

### Method 1: API Key Authentication

If you configured an `apiKey` in Pulumi config, include it in your requests:

**Via Query Parameter:**
```bash
curl "https://YOUR-FUNCTION-URL?measure=temperature&sensorID=sensor-001&value=23.5&apiKey=your-api-key"
```

**Via Header (Recommended):**
```bash
curl -H "X-API-Key: your-api-key" "https://YOUR-FUNCTION-URL?measure=temperature&sensorID=sensor-001&value=23.5"
```

### Method 2: Google Cloud IAM Authentication

If no API key is configured, the function requires Google Cloud IAM authentication. To grant access:

**Grant access to a service account:**
```bash
gcloud functions add-iam-policy-binding FUNCTION_NAME \
  --region=REGION \
  --member="serviceAccount:SERVICE_ACCOUNT_EMAIL" \
  --role="roles/cloudfunctions.invoker"
```

**Grant access to a user:**
```bash
gcloud functions add-iam-policy-binding FUNCTION_NAME \
  --region=REGION \
  --member="user:USER_EMAIL" \
  --role="roles/cloudfunctions.invoker"
```

**Authenticate requests using gcloud:**
```bash
gcloud auth print-identity-token | xargs -I {} curl \
  -H "Authorization: Bearer {}" \
  "https://YOUR-FUNCTION-URL?measure=temperature&sensorID=sensor-001&value=23.5"
```

**For service accounts, create and use an identity token:**
```bash
gcloud auth activate-service-account SERVICE_ACCOUNT_EMAIL --key-file=KEY_FILE
gcloud auth print-identity-token | xargs -I {} curl \
  -H "Authorization: Bearer {}" \
  "https://YOUR-FUNCTION-URL?measure=temperature&sensorID=sensor-001&value=23.5"
```

## Usage

### Recording a Reading

Send a GET request to the function URL with the following parameters:

- `measure`: Either `temperature` or `humidity`
- `sensorID`: Unique identifier for the sensor
- `value`: The measured value (numeric)
- `apiKey`: API key (if using API key authentication - can also use `X-API-Key` header)

**Example Request (with API key):**

```bash
curl "https://YOUR-FUNCTION-URL?measure=temperature&sensorID=sensor-001&value=23.5&apiKey=your-api-key"
```

**Example Request (with IAM auth):**

```bash
gcloud auth print-identity-token | xargs -I {} curl \
  -H "Authorization: Bearer {}" \
  "https://YOUR-FUNCTION-URL?measure=temperature&sensorID=sensor-001&value=23.5"
```

**Example Response (Success):**

```json
{
  "status": "success",
  "message": "Reading recorded successfully",
  "data": {
    "measure": "temperature",
    "sensorID": "sensor-001",
    "value": 23.5,
    "timestamp": "2024-01-15T10:30:00.123456",
    "document_id": "sensor-001_2024-01-15T10:30:00.123456"
  }
}
```

**Example Response (Error - Missing Parameter):**

```json
{
  "status": "error",
  "message": "Missing required parameter: sensorID"
}
```

**Example Response (Error - Authentication):**

```json
{
  "status": "error",
  "message": "Authentication required. Provide apiKey parameter or X-API-Key header."
}
```

### Firestore Structure

Readings are stored in the `readings` collection with the following structure:

```
readings/
  └── {sensorID}_{timestamp}/
      ├── measure: "temperature" | "humidity"
      ├── sensorID: string
      ├── value: number
      ├── timestamp: datetime
      └── created_at: server timestamp
```

## Development

### Local Testing

You can test the function locally using the Functions Framework:

```bash
cd function
pip install -r requirements.txt functions-framework
functions-framework --target=record_reading --debug
```

Then test with:

```bash
curl "http://localhost:8080?measure=temperature&sensorID=test-001&value=25.0"
```

### Updating the Function

1. Make changes to `function/main.py`
2. Run `pulumi up` to redeploy

## Cleanup

To remove all resources:

```bash
pulumi destroy
```

## Configuration Reference

| Config Key | Required | Default | Description |
|------------|----------|---------|-------------|
| `projectId` | Yes | - | Google Cloud Project ID |
| `region` | No | `us-central1` | GCP region for deployment |
| `firestoreConnection` | No | `{projectId}.appspot.com` | Firestore connection string |
| `apiKey` | No | - | API key for authentication (use `--secret` flag) |

## Troubleshooting

### Function deployment fails

- Ensure all required APIs are enabled
- Check that you have proper IAM permissions
- Verify the project ID is correct

### Function can't access Firestore

- Ensure Firestore is enabled in your project
- Check that the service account has `roles/datastore.user` permission
- Verify the connection string is correct
- **If you get a 403 error during deployment**, grant the Firestore permission manually:
  ```bash
  gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="serviceAccount:YOUR_PROJECT_ID@appspot.gserviceaccount.com" \
    --role="roles/datastore.user"
  ```

### Function returns 500 errors

- Check Cloud Function logs: `gcloud functions logs read`
- Verify environment variables are set correctly
- Ensure Firestore database exists and is accessible

### Function returns 401/403 errors

- If using API key: Verify the API key is correct and included in the request
- If using IAM: Ensure the caller has `roles/cloudfunctions.invoker` permission
- Check that authentication is properly configured

## License

MIT
