import json
import base64
import xml.etree.ElementTree as ET
import asyncio
from typing import Optional, List, Dict, Any
from pydantic import BaseModel


class YandexSearchConfig(BaseModel):
    api_key: str
    folder_id: str = "b1giur1tl3ajqq25bacd"
    search_type: str = "SEARCH_TYPE_RU"
    family_mode: str = "FAMILY_MODE_MODERATE"
    fix_typo_mode: str = "FIX_TYPO_MODE_ON"
    sort_mode: str = "SORT_MODE_BY_RELEVANCE"
    sort_order: str = "SORT_ORDER_DESC"
    group_mode: str = "GROUP_MODE_DEEP"
    groups_on_page: int = 5
    docs_in_group: int = 1
    max_passages: int = 3
    region: Optional[str] = "225"
    l10n: str = "LOCALIZATION_RU"
    response_format: str = "FORMAT_XML"
    grpc_host: str = "searchapi.api.cloud.yandex.net:443"


class YandexSearchAPI:
    def __init__(self, config: YandexSearchConfig):
        self.config = config

    async def search(self, query: str, page: int = 0) -> Optional[str]:
        """Асинхронный gRPC-запрос."""
        body = json.dumps({
            "query": {
                "search_type": self.config.search_type,
                "query_text": query,
                "family_mode": self.config.family_mode,
                "page": page,
                "fix_typo_mode": self.config.fix_typo_mode
            },
            "sort_spec": {
                "sort_mode": self.config.sort_mode,
                "sort_order": self.config.sort_order
            },
            "group_spec": {
                "group_mode": self.config.group_mode,
                "groups_on_page": self.config.groups_on_page,
                "docs_in_group": self.config.docs_in_group
            },
            "max_passages": self.config.max_passages,
            "region": self.config.region,
            "l10n": self.config.l10n,
            "folder_id": self.config.folder_id,
            "response_format": self.config.response_format,
            "user_agent": "Python gRPC Client"
        })

        grpc_command = [
            "grpcurl",
            "-rpc-header", f"Authorization: Api-Key {self.config.api_key}",
            "-d", body,
            self.config.grpc_host,
            "yandex.cloud.searchapi.v2.WebSearchService/Search"
        ]

        process = await asyncio.create_subprocess_exec(
            *grpc_command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            print(f"Ошибка gRPC-вызова: {stderr.decode()}")
            return None

        try:
            response_data = json.loads(stdout.decode())
            if "rawData" in response_data:
                decoded_data = base64.b64decode(response_data["rawData"]).decode("utf-8")
                return decoded_data
            else:
                print("Ошибка: rawData отсутствует в ответе")
                return None
        except Exception as e:
            print(f"Ошибка парсинга JSON: {e}")
            return None


class YandexSearchParser:
    @staticmethod
    def parse(xml_response: str) -> List[Dict[str, Any]]:
        """Парсит XML-ответ и извлекает документы."""
        root = ET.fromstring(xml_response)
        documents = []

        for doc in root.findall(".//doc"):
            title_elem = doc.find("title")
            title = "".join(title_elem.itertext()) if title_elem is not None else ""

            url = doc.find("url").text if doc.find("url") is not None else ""
            
            passages = []
            for passages_elem in doc.findall(".//passages"):
                for passage_elem in passages_elem.findall(".//passage"):
                    passages.append("".join(passage_elem.itertext()))
            
            extended_text_elem = doc.find(".//extended-text")
            extended_text = "".join(extended_text_elem.itertext()) if extended_text_elem is not None else ""
            
            documents.append({
                "title": title,
                "url": url,
                "passages": passages,
                "extended_text": extended_text
            })

        return documents
