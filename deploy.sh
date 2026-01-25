set -e

source .env


if [ -z "$PROJECT_ID" ] || [ -z "$FUNCTION_API_KEY" ]; then
    echo "PROJECT_ID and FUNCTION_API_KEY must be set"
    exit 1
fi

if [ -z "$REGION" ]; then
    echo "REGION must be set"
    exit 1
fi

gcloud config set project $PROJECT_ID

pulumi stack select pilvikala-org/temp-recorder/temp-recorder

pulumi config set temp-recorder:projectId $PROJECT_ID
pulumi config set --secret apiKey $FUNCTION_API_KEY
pulumi config set region $REGION

pulumi up

echo "Function URL: $(pulumi stack output function_url)"