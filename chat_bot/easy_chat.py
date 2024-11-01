import os, re
from urllib.parse import unquote
from typing import Union, List
from openai import AzureOpenAI
from openai.types.chat import ChatCompletion
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
import json

"""
Environment variables used for EasyChatClient Auto-Configuration:
OPENAI_API_BASE             Required
OPENAI_API_KEY              Optional, if not set will use default credential
OPENAI_DEPLOYMENT_NAME      Optional, default is 'gpt-4o'
OPENAI_EMBEDDING_DEPLOYMENT_NAME    Optional, default is 'text-embedding-ada-002'
AZURESEARCH_API_BASE        Required
AZURESEARCH_API_KEY         Optional, if not set will use managed identity of open ai
AZURESEARCH_INDEX_NAME      Optiona, default is 'documents'
"""


def get_json_serializable_data(completion : ChatCompletion) -> dict:
    data = {
        "choices": [ ],
        "created": completion.created,
        "id": completion.id,
        "model": completion.model,
        "object": completion.object,
        "system_fingerprint": completion.system_fingerprint,
        "usage": {
            "completion_tokens":  completion.usage.completion_tokens,
            "prompt_tokens":  completion.usage.prompt_tokens,
            "total_tokens":  completion.usage.total_tokens,
        }
    }
    for choice in completion.choices:
        c = {
            "finish_reason": choice.finish_reason,
            "index": choice.index,
            #"logprobs": choice.logprobs,
            "message": {
                "refusal": choice.message.refusal,
                "role": choice.message.role,
                "content": choice.message.content,
                "end_turn": choice.message.end_turn,
                "context": choice.message.context
                # other fields: function_call, tool_calls, audio
            }
        }
        # check if itent exists and is a string
        if "intent" in c["message"]["context"] and isinstance(c["message"]["context"]["intent"], str):
            try:
                c["message"]["context"]["intent"] = json.loads( c["message"]["context"]["intent"])
            except:
                pass
        # check if citations exists and parse the information on pages and storage account
        if "citations" in c["message"]["context"] and isinstance(c["message"]["context"]["citations"], list):
            for citation in c["message"]["context"]["citations"]:
                try:
                    citation["pages"] = re.findall(r'_pages_(\d+)', citation["filepath"] )
                    if citation["url"].lower().startswith("http"):
                        urlParts = citation["url"].split("/")
                        if len(urlParts) >= 4:
                            citation["storageaccount_name"] = urlParts[2].split(".")[0]
                            citation["storageaccount_container"] = urlParts[3]
                            citation["storageaccount_blob"] = unquote("/".join(urlParts[4:]).split("?")[0].split("#")[0])
                except:
                    pass
        data["choices"].append(c)
    return data

class EasyChatMessage:
    role: str
    content: str
    def __init__(self, role: str, content: str):
        role = str(role).strip().lower()
        if role not in ['system', 'user', 'assistant']:
            raise ValueError("role must be 'system', 'user' or 'assistant'")
        self.role = role
        self.content = content


class EasyChatClient:
    _open_ai_client: AzureOpenAI
    _open_ai_deployment_name: str
    _open_ai_embedding_deployment_name: str
    _azure_search_api_base: str
    _azure_search_api_key: str
    _azure_search_index_name: str
    _semantic_configuration: str
    _filter: str = ""
    
    def __init__(
        self,
        open_ai_client : Union[AzureOpenAI, None] = None,
        open_ai_deployment_name: Union[None, str] = None,
        open_ai_embedding_deployment_name: Union[None, str] = None,
        azure_search_api_base: Union[None, str] = None,
        azure_search_index_name: Union[None, str] = None,
        azure_search_api_key: Union[None, str] = None,
        semantic_configuration: Union[None, str] = None
    ):
        """
        Create a new EasyChatClient

        :param open_ai_client: AzureOpenAI, optional, if not set, will use default credential
        :param open_ai_deployment_name: str, optional, default is 'gpt-4o'
        :param open_ai_embedding_deployment_name: str, optional, default is 'text-embedding-ada-002'
        :param azure_search_api_base: str, required
        :param azure_search_index_name: str, optional, default is 'documents'
        :param azure_search_api_key: str, optional, if not set will use managed identity of open ai
        :returns EasyChatClient
        :raises ValueError: if azure_search_api_base or open_ai_client is not set
        """

        if isinstance(open_ai_client, AzureOpenAI):
            self._open_ai_client = open_ai_client
        else:
            if os.getenv("OPENAI_API_BASE") is None or os.getenv("OPENAI_API_BASE") == "":
                raise ValueError("OPENAI_API_BASE is required")
            if os.getenv("OPENAI_API_KEY") is None:
                self._open_ai_client = AzureOpenAI(
                    azure_endpoint = os.getenv("OPENAI_API_BASE"),
                    azure_ad_token_provider = get_bearer_token_provider(DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default"),
                    api_version = "2024-02-01"
                )
            else:
                self._open_ai_client = AzureOpenAI(
                    azure_endpoint = os.getenv("OPENAI_API_BASE"),
                    api_key = os.getenv("OPENAI_API_KEY"),
                    api_version = "2024-02-01"
                )
        
        # api_key: if none, try to get from env
        if azure_search_api_key is None:
            azure_search_api_key = os.getenv("AZURESEARCH_API_KEY")
        # api_key is optional, if not set, we use managed identity
        if azure_search_api_key is None:
            azure_search_api_key = ""
        self._azure_search_api_key = str(azure_search_api_key)

        # api_base: if none, try to get from env
        if azure_search_api_base is None:
            azure_search_api_base = os.getenv("AZURESEARCH_API_BASE")
        # api_base is required
        if azure_search_api_base is None or azure_search_api_base == "":
            raise ValueError("AZURESEARCH_API_BASE is required")
        self._azure_search_api_base = str(azure_search_api_base)

        # index_name: if none, try to get from env
        if azure_search_index_name is None:
            azure_search_index_name = os.getenv("AZURESEARCH_INDEX_NAME")
        # index_name is optional
        if azure_search_index_name is None or azure_search_index_name == "":
            azure_search_index_name = "documents"
        self._azure_search_index_name = str(azure_search_index_name)

        # open_ai_deployment_name: if none, try to get from env
        if open_ai_deployment_name is None:
            open_ai_deployment_name = os.getenv("OPENAI_DEPLOYMENT_NAME")
        # open_ai_deployment_name is optional
        if open_ai_deployment_name is None or open_ai_deployment_name == "":
            open_ai_deployment_name = "gpt-4o"
        self._open_ai_deployment_name = str(open_ai_deployment_name)

        # open_ai_embedding_deployment_name: if none, try to get from env
        if open_ai_embedding_deployment_name is None:
            open_ai_embedding_deployment_name = os.getenv("OPENAI_EMBEDDING_DEPLOYMENT_NAME")
        # open_ai_embedding_deployment_name is optional
        if open_ai_embedding_deployment_name is None or open_ai_embedding_deployment_name == "":
            open_ai_embedding_deployment_name = "text-embedding-ada-002"
        self._open_ai_embedding_deployment_name = str(open_ai_embedding_deployment_name)

        # semantic_configuration: if none, try to get from env
        if semantic_configuration is None or semantic_configuration == "":
            semantic_configuration = f"{self._azure_search_index_name}-semantic-configuration"
        self._semantic_configuration = str(semantic_configuration)
        
    def setSearchFilter(self, filter : str):
        self._filter = str(filter)
    def getSearchFilter(self) -> str:
        return self._filter
    
    def chat(self, messages: List[EasyChatMessage]) -> dict:
        dataSource = {
            "type": "azure_search",
            "parameters": {
                "endpoint": self._azure_search_api_base,
                "index_name": self._azure_search_index_name,
                "top_n_documents": 5,
                "role_information": "You must generate citation based on the retrieved information.",
                "fields_mapping": {
                    "filepath_field": "chunk_id",
                    "url_field": "metadata_storage_path"
                },
                "embedding_dependency": {
                    "type": "deployment_name",
                    "deployment_name": self._open_ai_embedding_deployment_name
                },
                "query_type": "vector_semantic_hybrid",
                "semantic_configuration": self._semantic_configuration
            }
        }
        # setting authentication
        if self._azure_search_api_key == "":
            dataSource["parameters"]["authentication"] = {
                "type": "system_assigned_managed_identity"
            }
        else:
            dataSource["parameters"]["authentication"] = {
                "type": "api_key",
                "api_key": self._azure_search_api_key
            }
        # setting filter
        if self._filter != "":
            dataSource["parameters"]["filter"] = str(self._filter)

        completion = self._open_ai_client.chat.completions.create(
            model = self._open_ai_deployment_name,
            messages = [
                {
                    "role": message.role,
                    "content": message.content,
                } for message in messages
            ],
            temperature=0.2,
            extra_body= {
                "data_sources": [ dataSource ]
            }
        )
        return get_json_serializable_data(completion)


def dict_to_chat_messages(data: dict) -> List[EasyChatMessage]:
    if "messages" in data:
        return [ EasyChatMessage(message["role"], message["content"]) for message in data["messages"] ]
    return []
