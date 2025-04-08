import os
import config
from azure.storage.blob import BlobServiceClient

# Load values from env or config
AZURE_CONTAINER_NAME = os.getenv("AZURE_CONTAINER_NAME", "legal-files")
AZURE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")

def get_blob_service_client():
    if not AZURE_CONNECTION_STRING:
        raise ValueError("AZURE_STORAGE_CONNECTION_STRING is not set in environment variables.")
    return BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)

def upload_file(local_path, blob_name):
    blob_service = get_blob_service_client()
    container_client = blob_service.get_container_client(AZURE_CONTAINER_NAME)

    # Create container if not exists
    try:
        container_client.create_container()
    except Exception:
        pass

    blob_client = container_client.get_blob_client(blob_name)
    with open(local_path, "rb") as f:
        blob_client.upload_blob(f, overwrite=True)
    print(f"[Azure Blob] Uploaded: {blob_name}")

def download_file(blob_name, local_path):
    blob_service = get_blob_service_client()
    blob_client = blob_service.get_container_client(AZURE_CONTAINER_NAME).get_blob_client(blob_name)

    with open(local_path, "wb") as f:
        data = blob_client.download_blob()
        f.write(data.readall())
    print(f"[Azure Blob] Downloaded: {blob_name}")

def delete_file(blob_name):
    blob_service = get_blob_service_client()
    blob_client = blob_service.get_container_client(AZURE_CONTAINER_NAME).get_blob_client(blob_name)
    blob_client.delete_blob()
    print(f"[Azure Blob] Deleted: {blob_name}")

def list_files():
    blob_service = get_blob_service_client()
    container_client = blob_service.get_container_client(AZURE_CONTAINER_NAME)
    return [blob.name for blob in container_client.list_blobs()]
