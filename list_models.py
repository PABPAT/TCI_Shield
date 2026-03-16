import boto3

# Connect to Bedrock (not bedrock-runtime) to list models
client = boto3.client(
    service_name="bedrock",
    region_name="us-east-1"
)

# Get all available foundation models
response = client.list_foundation_models()

# Filter and print only Nova models
print("Available Nova Models on your account:")
print("-" * 50)
for model in response["modelSummaries"]:
    if "nova" in model["modelId"].lower():
        print(model["modelId"])