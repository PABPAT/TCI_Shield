import boto3
import json

# Creating a client to connect with AWS.
client = boto3.client(
    service_name="bedrock-runtime",
    region_name="us-east-1",
)

# Hardcoded message to AWS Nova. Later we will change this to dynamic.
# Using Voice Input, Web Chat UI, Agent orchestrator passing context.
message = ("I am a UK-based business that sells goods to buyers in Europe on Net 60 payment terms. "
           "My annual turnover is £5 million. Can you explain what trade credit insurance is and "
           "why I might need it?")

# Call Nova Lite - invoke model and capture response.
response = client.invoke_model(
    modelId = "amazon.nova-lite-v1:0",
    body = json.dumps({
        "messages": [
        {
            "role" : "user",
            "content" :[{"text" : message}]
        }
    ],
    "inferenceConfig" : {
        "maxTokens" : 500,
        "temperature" : 0.7
    }
    }),
)

# Parse the response.
result = json.loads(response['body'].read())

# Extract Nova's reply from the response structure.
reply = result["output"]["message"]["content"][0]["text"]

# Print the result
print("Nova Lite says:")
print("-" * 50)
print(reply)

# Print token usage to track the costs
usage = result["usage"]
print(f"\nTokens used - Input: {usage['inputTokens']} | Output: {usage['outputTokens']}")

