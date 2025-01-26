import oci.object_storage


def create_object_storage_client(oci_cfg, signer):
    """
    Creates an OCI Object Storage client using the provided configuration and signer.

    Args:
        oci_cfg (dict): The OCI configuration dictionary, typically loaded from a config file.
        signer (oci.signer.Signer): The signer to authenticate API requests, often required for resource authorization.

    Returns:
        oci.object_storage.ObjectStorageClient: An instance of the OCI Object Storage client.
    """
    return oci.object_storage.ObjectStorageClient(config=oci_cfg, signer=signer)


def put_file_to_object_storage_image(object_storage_client,
                                     file_content: bytes,
                                     namespace: str,
                                     bucket_name: str,
                                     object_name: str,
                                     content_type: str):
    """
    Uploads a file to OCI Object Storage with a specified content type.

    Args:
        object_storage_client (oci.object_storage.ObjectStorageClient): The OCI Object Storage client.
        file_content (bytes): The content of the file to be uploaded.
        namespace (str): The Object Storage namespace where the bucket resides.
        bucket_name (str): The name of the bucket where the file will be uploaded.
        object_name (str): The name of the object (file) in the bucket.
        content_type (str): The MIME type of the file, e.g., "image/jpeg" or "image/png".

    Returns:
        int: The HTTP status code of the response.
    """
    response = object_storage_client.put_object(
        namespace,
        bucket_name,
        object_name,
        file_content,
        content_type=content_type
    )
    return response.status


def create_read_only_object_par(object_storage_client,
                                par_name: str,
                                namespace: str,
                                bucket_name: str,
                                object_name: str,
                                object_expiry_time):
    """
    Creates a read-only Pre-Authenticated Request (PAR) for an object in OCI Object Storage.

    Args:
        object_storage_client (oci.object_storage.ObjectStorageClient): The OCI Object Storage client.
        par_name (str): A name to identify the Pre-Authenticated Request.
        namespace (str): The Object Storage namespace where the bucket resides.
        bucket_name (str): The name of the bucket where the object resides.
        object_name (str): The name of the object for which the PAR is created.
        object_expiry_time (datetime): The expiration time of the PAR.

    Returns:
        tuple:
            - status (int): The HTTP status code of the response.
            - par_url (str or None): The full URL of the Pre-Authenticated Request, or None if not available.
    """

    par_details = oci.object_storage.models.CreatePreauthenticatedRequestDetails(
        name=par_name,
        access_type="ObjectRead",  # Set to ObjectRead to allow read-only access
        bucket_listing_action="Deny",  # Deny bucket listing for security
        object_name=object_name,  # Set to the specific object name
        time_expires=object_expiry_time  # Set expiration for the PAR
    )

    # Create the PAR in the specified bucket
    response = object_storage_client.create_preauthenticated_request(namespace, bucket_name, par_details)
    return response.status, response.data.full_path if response.data and response.data.full_path else None

