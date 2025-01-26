import io
import json
import logging
import datetime
from datetime import timedelta

from fdk import response

import io
import json

def handler(ctx, data: io.BytesIO = None):
    """
    Simple example of an OCI Function used to do API Key validation.

    Here, the valid API keys are Hard-coded in the function. This could be improved by fetching values from a
    persistent storage like a DB or an OCI vault.

    Args:
        ctx: The context object provided by OCI Functions, containing metadata and configurations.
        data : The JSON string payload containing details about the OCI event and the image to process.
    """    
    logging.getLogger().setLevel(logging.INFO)
    logging.getLogger().info(data.getvalue().decode('utf-8'))

    # Hard-coded set of API Keys
    valid_api_keys = ["11cb5027-28d2-4359-b8e8-cc209a963a0d",
                      "6340df79-56c7-401d-b6d0-2cdfb0591ea6",
	                  "58717bb9-44a1-4072-b498-c78c22a85919"]

    try:
        auth_token = json.loads(data.getvalue())
        token = auth_token.get("data").get("api-key")
        
        if token in valid_api_keys:
            # Authenticated
            logging.getLogger().info("Result: Authorized")
            return response.Response(
                ctx, 
                status_code=200, 
                response_data=json.dumps({"active": True})
            )
    
    except (Exception, ValueError) as ex:
        logging.getLogger().info('error parsing json payload: ' + str(ex))
        pass
    
    logging.getLogger().info("Result: Unauthorized")
    return response.Response(
        ctx, 
        status_code=401, 
        response_data=json.dumps({"active": False, "wwwAuthenticate": "API-key"})
    )
