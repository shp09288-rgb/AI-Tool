import base64
from typing import Any

import httpx


class SalesforceHttpClient:
    """Access token is injected from the outside."""

    def __init__(self, instance_url: str, access_token: str, api_version: str = "v59.0") -> None:
        self.instance_url = instance_url.rstrip("/")
        self.api_version = api_version
        self._access_token = access_token
        self._client = httpx.Client(
            base_url=self.instance_url,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            timeout=60.0,
        )

    def get_sobject(self, object_name: str, record_id: str, fields: list[str] | None = None) -> dict[str, Any]:
        params: dict[str, str] = {}
        if fields:
            params["fields"] = ",".join(fields)
        response = self._client.get(
            f"/services/data/{self.api_version}/sobjects/{object_name}/{record_id}",
            params=params,
        )
        response.raise_for_status()
        return response.json()

    def query(self, soql: str) -> dict[str, Any]:
        response = self._client.get(
            f"/services/data/{self.api_version}/query",
            params={"q": soql},
        )
        response.raise_for_status()
        return response.json()

    def patch_sobject(self, object_name: str, record_id: str, body: dict[str, Any]) -> None:
        response = self._client.patch(
            f"/services/data/{self.api_version}/sobjects/{object_name}/{record_id}",
            json=body,
        )
        response.raise_for_status()

    def post_sobject(self, object_name: str, body: dict[str, Any]) -> dict[str, Any]:
        response = self._client.post(
            f"/services/data/{self.api_version}/sobjects/{object_name}/",
            json=body,
        )
        response.raise_for_status()
        return response.json()

    def create_content_version(
        self,
        *,
        title: str,
        path_on_client: str,
        first_publish_location_id: str,
        version_data_b64: str,
    ) -> dict[str, Any]:
        """Files 업로드 + 레코드 연결 (FirstPublishLocationId)."""
        body = {
            "Title": title,
            "PathOnClient": path_on_client,
            "ContentLocation": "S",
            "FirstPublishLocationId": first_publish_location_id,
            "VersionData": version_data_b64,
        }
        return self.post_sobject("ContentVersion", body)

    def create_content_version_from_bytes(
        self,
        *,
        title: str,
        path_on_client: str,
        first_publish_location_id: str,
        data: bytes,
    ) -> dict[str, Any]:
        return self.create_content_version(
            title=title,
            path_on_client=path_on_client,
            first_publish_location_id=first_publish_location_id,
            version_data_b64=base64.b64encode(data).decode("ascii"),
        )

    def close(self) -> None:
        self._client.close()

