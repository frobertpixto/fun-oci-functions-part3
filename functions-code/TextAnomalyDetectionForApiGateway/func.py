import io
import json
import logging
import sys
import decimal
import uuid
import oci

from datetime import datetime, timedelta
from fdk import response

from oci_utils.url_utils import get_image_data_from_url
from oci_utils.oci_object_storage import create_object_storage_client, put_file_to_object_storage_image, \
    create_read_only_object_par
from oci_utils.oci_ai import detect_text_from_oject_storage_image
from oci_utils.oci_functions import invoke_function
from oci_utils.oci_document_generator import prepare_document_generator_payload, build_output_pdf_name

# Setting the decimal context to round down, to ease the Display of fraction
decimal.getcontext().rounding = decimal.ROUND_DOWN

# Configure logging to output debug information to the standard output stream.
logging.basicConfig(stream=sys.stdout, level=logging.INFO)

# The compartment ID in Oracle Cloud Infrastructure under which operations will be performed. <<<
compartment_id = "ocid1.compartment.oc1..zzz"

# The Oracle Cloud ID (OCID) for the Document Generator function. <<<
fn_ocid = "ocid1.fnfunc.oc1.iad..zzz"

fontfile_name = "part3/Monoton.zip"
template_name = "part3/TextAnomalyTemplate.docx"

# Create a signer object using the Cloud Shell Resource Principal for authenticating requests.
signer = oci.auth.signers.get_resource_principals_signer()
oci_config= {}

#
# Utility Functions
#

def all_texts_are_clear_in_the_image(detect_text_response: dict, confidence_level: float = 0.90):
    """
    Checks if all detected texts in an image meet a specified confidence level.

    Args:
        detect_text_response (dict): The response dictionary from text detection containing words and their confidence.
        confidence_level (float): The minimum confidence level required for each text to be considered clear.

    Returns:
        bool: True if all texts have a confidence level above the specified threshold, False otherwise.
    """
    words = detect_text_response.get("image_text", {}).get("words", [])
    return all(word.get("confidence", 0) >= confidence_level for word in words)


def generate_doc_gen_data_content_from_ai_response(detect_text_response: dict, bucket_name: str, namespace: str,
                                                   object_name: str):
    """
    Transforms text detection response into a format suitable for generating documents with the OCI Document Generator.

    Args:
        detect_text_response (dict): The response from the text detection API.
        bucket_name (str): The name of the OCI Object Storage bucket where the image is stored.
        namespace (str): The namespace of the OCI Object Storage where the bucket resides.
        object_name (str): The name of the object (image) in the bucket for which text detection was performed.

    Returns:
        dict: A dictionary formatted to be used as payload for document generation.
    """
    words = detect_text_response.get("image_text", {}).get("words", [])
    data_content = {
        "image_with_anomalies": {
            "source": "OBJECT_STORAGE",
            "objectName": object_name,
            "namespace": namespace,
            "bucketName": bucket_name,
            "mediaType": "image/png",
            "height": "450px"
        },
        "words": [
            {
                "word": word.get("text"),
                "confidence": round(word.get("confidence", 0) * 100, 1),
                "corner1": {
                    "x": round(word.get("bounding_polygon", {}).get("normalized_vertices", [])[0].get("x", 0), 2),
                    "y": round(word.get("bounding_polygon", {}).get("normalized_vertices", [])[0].get("y", 0), 2)
                },
                "corner3": {
                    "x": round(word.get("bounding_polygon", {}).get("normalized_vertices", [])[2].get("x", 0), 2),
                    "y": round(word.get("bounding_polygon", {}).get("normalized_vertices", [])[2].get("y", 0), 2)
                }
            }
            for word in words
        ]
    }
    return data_content


def prepare_response(ctx, response_payload, status_code: int = 200):
    return response.Response(
                ctx, 
                status_code=status_code,
                response_data=json.dumps(response_payload),
                headers={"Content-Type": "application/json"})


def generate_error_response(ctx, error_message: str):
    logging.error(error_message)
    return prepare_response(ctx, {"message":error_message}, status_code=400)


def handler(ctx, data: io.BytesIO = None):
    """
    1. Parse Input data to obtain the Image URL to process
    2. Read the Image from URL to memory.
    3. Store the image in Bucket.
    4. Call ML text Detection using Image from Bucket
    5. Check if Anomalies exist
    6. Generate a PDF report using the OCI Document generator PBF
    7. Create PAR from Bucket PDF.
    8. Return PAR in response with status code 200. If No PDF generated, return status code 204.

    Args:
        ctx: The context object provided by OCI Functions, containing metadata and configurations.
        data (str): The JSON string payload containing details about the image to process.
    """
    logging.info("Inside Python Text Anomaly Detection function (for API Gateway)")

    if data is None:
        message = "No data provided"
        logging.error(message)
        return prepare_response(ctx, message)

    try:
        #
        # 1. Parse the event data to extract necessary details for processing.
        #
        payload = json.loads(data.getvalue())
        logging.info(f"Received payload: {json.dumps(payload)}")

        bucket_name = "fun_oci_functions_bucket"
        namespace = "idsvv7k2bdum"
        url = payload["url"]

        object_storage_client = create_object_storage_client(oci_config, signer=signer)

        #
        # 2. Read Image data from URL
        #
        url_status_code, file_content, file_name, content_type = get_image_data_from_url(url)

        if url_status_code != 200:
            return generate_error_response(ctx, f"Failed to retrieve the file from '{url}'. Status code: {url_status_code}")

        if content_type != "image/jpeg" and content_type != "image/png":
            return generate_error_response(ctx, f"Failed to retrieve a jpeg or png image from '{url}'.")

        #
        # 3. Store the image in a Bucket
        #
        image_name = "part3/" + str(uuid.uuid4()) + "-" + file_name  # The name you want to assign to the object in OCI
        object_storage_response = put_file_to_object_storage_image(object_storage_client,
                                                                   file_content=file_content,
                                                                   namespace=namespace,
                                                                   bucket_name=bucket_name,
                                                                   object_name=image_name,
                                                                   content_type=content_type)

        if object_storage_response != 200:
            return generate_error_response(ctx, f"Image {image_name} storing in Bucket {bucket_name} failed with status code {object_storage_response}.")

        logging.info(f"Image {image_name} stored successfully in Bucket {bucket_name}")
        logging.info(f'Processing Image: "{image_name}" from Bucket: "{bucket_name}" in Namespace: "{namespace}"')

        #
        # 4. Detect texts in the specified object storage image.
        #
        detect_text_response = detect_text_from_oject_storage_image(oci_config, signer, compartment_id, namespace,
                                                                    bucket_name, image_name)
        logging.debug(f"detect_text_response: {detect_text_response}")

        #
        # 5. Do we have anomalies in some detected Words
        #
        if all_texts_are_clear_in_the_image(detect_text_response):
            response_message = f'All Words are clear in Image: "{image_name}" from Bucket: "{bucket_name}" in Namespace: "{namespace}"'
            logging.info(
                f'{response_message}. Processing Complete')
            
            # Return a 204 indicating that no Anomalies are found. 
            return prepare_response(ctx, {"message":response_message}, status_code=204)
        else:
            logging.info(
                f'Anomalies found in Image: "{image_name}". Generating PDF Document')

        #
        # 6. Generate a PDF report using the OCI Document generator PBF
        #

        # Generate the Data that will be in the report based on AI Text analysis.
        data_content = generate_doc_gen_data_content_from_ai_response(detect_text_response, bucket_name, namespace,
                                                                      image_name)

        # Prepare payload for the Document Generator function.
        doc_gen_fn_payload = prepare_document_generator_payload(data_content, namespace, bucket_name, image_name,
                                                                fontfile_name, template_name)

        # Invoke the Document Generator function
        response = invoke_function(oci_config, signer, fn_ocid, doc_gen_fn_payload)
        document_generator_response = response.content.decode()
        logging.debug(f"DocGen Response: status code: {response.status_code}, result: {document_generator_response}")

        # Handling response and logging based on the statuses.
        if response.status_code == 200:  # This is the Function HTTP response
            document_generator_response_dict = json.loads(document_generator_response)
            app_response_code = document_generator_response_dict.get("code")
            if app_response_code == 200:  # This is the Document generation application response
                logging.info("Document generated successfully")
            else:
                return generate_error_response(ctx, f"Document generation failure: '{app_response_code}'. See Application Log")

        #
        # 7. Create PAR with the expiration date and time in 1 Hour from now.
        #
        par_status_code, par_full_path = create_read_only_object_par(object_storage_client,
                                                                     "PAR_for_report",
                                                                     namespace=namespace,
                                                                     bucket_name=bucket_name,
                                                                     object_name=build_output_pdf_name(image_name),
                                                                     object_expiry_time=datetime.utcnow() + timedelta(
                                                                         hours=1))

        if par_status_code != 200:
            return generate_error_response(ctx, f"PAR generation error. Status code: {par_status_code}")

        logging.info(f"Pre-Authenticated Request URL: {par_full_path}")

        #
        # 8. Prepare response that includes the PAR URL for the Anomaly PDF report.
        #
        response_payload = {
            "inputUrl": url,
            "reportWithAnomalies": par_full_path
        }

        return prepare_response(ctx, response_payload)

    except Exception as ex:
        # Log any exceptions that occur during processing.
        logging.info('Error in handler: ' + str(ex))
        raise
