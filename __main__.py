import pulumi
import pulumi_gcp as gcp

# Get configuration
config = pulumi.Config()
project_id = config.require("projectId")
region = config.get("region") or "us-central1"

# Get Firestore connection string from config (optional, defaults to project default)
firestore_connection = config.get("firestoreConnection") or f"{project_id}.appspot.com"

# Get API key for authentication (optional - if not set, will use IAM auth only)
api_key = config.get_secret("apiKey")  # Use get_secret to keep it secure

# Create a storage bucket for the Cloud Function source code
bucket = gcp.storage.Bucket(
    "function-source-bucket",
    location=region,
    force_destroy=True,
    uniform_bucket_level_access=True,
    project=project_id
)

# Create a zip file of the function code
source_archive = gcp.storage.BucketObject(
    "function-source",
    bucket=bucket.name,
    source=pulumi.FileArchive("./function")
)

# Get the default service account email
# Cloud Functions use the App Engine default service account by default
# Format: {PROJECT_ID}@appspot.gserviceaccount.com
default_service_account_email = f"{project_id}@appspot.gserviceaccount.com"

# Create Firestore database (if it doesn't exist)
# Note: Firestore database creation is a one-time operation per project
# If the database already exists, this will be a no-op
firestore_database = gcp.firestore.Database(
    "temp-recorder-database",
    project=project_id,
    location_id=region,  # Use the same region as the function
    type="FIRESTORE_NATIVE",  # Use Firestore Native mode (recommended)
    name="(default)",  # Use the default database name
)

# Create the Cloud Function (using v2 API for HTTP triggers)
# For HTTP-triggered functions, we don't specify event_trigger
function = gcp.cloudfunctionsv2.Function(
    "temp-recorder-function",
    location=region,
    project=project_id,
    build_config=gcp.cloudfunctionsv2.FunctionBuildConfigArgs(
        runtime="python311",
        entry_point="record_reading",
        source=gcp.cloudfunctionsv2.FunctionBuildConfigSourceArgs(
            storage_source=gcp.cloudfunctionsv2.FunctionBuildConfigSourceStorageSourceArgs(
                bucket=bucket.name,
                object=source_archive.name,
            ),
        ),
    ),
    service_config=gcp.cloudfunctionsv2.FunctionServiceConfigArgs(
        available_memory="256M",
        timeout_seconds=60,
        environment_variables=pulumi.Output.all(api_key).apply(
            lambda args: {
                "FIRESTORE_CONNECTION": firestore_connection,
                "GOOGLE_CLOUD_PROJECT": project_id,
                **({"API_KEY": args[0]} if args[0] else {}),
            }
        ),
        service_account_email=default_service_account_email,
    ),
)

# Authentication options:
# Option 1: Require Google Cloud IAM authentication (recommended for production)
# Option 2: Use API key validation in function code (set apiKey config)
# Option 3: Allow public access (NOT recommended - remove this block)

# For IAM authentication, grant access to specific service accounts or users:
# Example: Grant access to a service account
# invoker = gcp.cloudfunctionsv2.FunctionIamMember(
#     "function-invoker",
#     project=function.project,
#     location=function.location,
#     cloud_function=function.name,
#     role="roles/cloudfunctions.invoker",
#     member="serviceAccount:your-service-account@project.iam.gserviceaccount.com",
# )

# For public access (NOT RECOMMENDED - only for testing):
# Uncomment the following if you need public access (and use API key in function code):
invoker = gcp.cloudfunctionsv2.FunctionIamMember(
    "function-invoker",
    project=function.project,
    location=function.location,
    cloud_function=function.name,
    role="roles/cloudfunctions.invoker",
    member="allUsers",
)

# Grant the Cloud Function permission to access Firestore
# NOTE: This requires project-level IAM permissions. If you get a 403 error, you can:
# 1. Grant the permission manually using gcloud:
#    gcloud projects add-iam-policy-binding PROJECT_ID \
#      --member="serviceAccount:PROJECT_ID@appspot.gserviceaccount.com" \
#      --role="roles/datastore.user"
# 2. Or ask your project admin to grant you the "Resource Manager Project IAM Admin" role
# 3. Or the default App Engine service account may already have Firestore permissions
#
# Uncomment the following if you have the necessary permissions:
firestore_user = gcp.projects.IAMMember(
    "firestore-user",
    project=project_id,
    role="roles/datastore.user",
    member=pulumi.Output.from_input(f"serviceAccount:{default_service_account_email}"),
)

firestore_reader_service_account = gcp.serviceaccount.Account(
    "firestore-reader-sa",
    account_id="firestore-reader-sa",
    display_name="Firestore Reader Service Account",
    project=project_id,
)

# Grant the service account permission to read from Firestore
firestore_reader = gcp.projects.IAMMember(
    "firestore-reader",
    project=project_id,
    role="roles/datastore.user",
    member=firestore_reader_service_account.email.apply(lambda email: f"serviceAccount:{email}"),
)

# Export the function URL
# For v2 functions, the URL is in the service config
pulumi.export("function_url", function.service_config.apply(lambda sc: sc.uri if sc else ""))
pulumi.export("function_name", function.name)
pulumi.export("project_id", project_id)
pulumi.export("firestore_database_name", firestore_database.name)
