from google import genai

from google.genai import types

from kubernetes import client,config

config.load_kube_config(
    context="kind-gitops-cluster"
)

v1 = client.CoreV1Api()

print(v1.api_client.configuration.host)

client = genai.Client()

def get_pods():
    pods = v1.list_pod_for_all_namespaces()

    return [
        pod.metadata.name
        for pod in pods.items
    ]

print(get_pods())

def get_cluster_name():
    return "gitops-cluster"

tool_registry = {
    "get_pods" : get_pods,
    "get_deployment_status" : get_deployment_status,
    "get_pod_logs" : get_pod_logs,
    "get_pod_events" : get_pod_events
}


# Tell Gemini about the function
get_cluster_name_declaration = {
    "name" : "get_cluster_name",
    "description" : "Return the name of the Kubernetes cluster."
}

# Give the function declaration to Gemini
tools = types.Tool(
    function_declarations = [get_cluster_name_declaration]
)

config = types.GenerateContentConfig(
    tools = [tools],
    automatic_function_calling = types.AutomaticFunctionCallingConfig(
        disable = True
    )
)

#Ask gemini something that requires our tool
response = client.models.generate_content(
    model = "gemini-3.6-flash",
    contents = "What kubernetes cluster am i using? use the get_cluster_name tool.",
    config = config
)

#check what gemini requested
print("Gemini response:")

for function_call in response.function_calls:
    
    function_name = function_call.name
    
    tool_function = tool_registry[function_name]
    
    result = tool_function()
        
    tool_response = types.Part.from_function_response(
        name = function_call.name,
        response = {"result": result}
    )
        
    final_response = client.models.generate_content(
        model = "gemini-3.6-flash",
        contents = [
            "What kubernetes am i using?",
            response.candidates[0].content,
            tool_response,
        ],
        config = config,
    )
       
    print("Final Gemini Response: ")
    print(final_response.text)