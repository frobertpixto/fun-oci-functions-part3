import mimetypes
import requests


def get_image_content_type(filename: str) -> str:
    """
    Determine the content type of an image file based on its extension.

    Args:
        filename (str): The name of the image file.

    Returns:
        str: The content type ("image/jpeg" or "image/png") if recognized, otherwise None.
    """
    # Guess the MIME type based on the file extension
    mime_type, _ = mimetypes.guess_type(filename)

    # Check for recognized content types
    if mime_type == "image/jpeg":
        return "image/jpeg"
    elif mime_type == "image/png":
        return "image/png"
    else:
        return None


def get_data_from_url(url: str):
    """
    Fetches data from a given URL and extracts the file name.

    Args:
        url (str): The URL to fetch data from.

    Returns:
        tuple:
            - status_code (int): The HTTP status code of the response.
            - content (bytes): The content of the response, in bytes.
            - file_name (str): The extracted file name from the URL.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.88 Safari/537.36",
        "Accept": "*/*",
    }

    file_name = url.split('/')[-1]

    # Download the file from URL into memory
    get_url_response = requests.get(url, headers=headers)
    return get_url_response.status_code, get_url_response.content, file_name


def get_image_data_from_url(url: str):
    """
    Fetches image data from a URL and determines its content type.

    Args:
        url (str): The URL to fetch image data from.

    Returns:
        tuple:
            - status_code (int): The HTTP status code of the response.
            - content (bytes): The content of the image, in bytes.
            - file_name (str): The extracted file name from the URL.
            - content_type (str): The content type of the image
              (e.g., "image/jpeg" or "image/png"). Returns None if the
              content type is not recognized.
    """
    status_code, content, file_name = get_data_from_url(url)

    content_type = get_image_content_type(file_name)
    return status_code, content, file_name, content_type
