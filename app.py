import os
import io
import json
import logging
import requests
from http import HTTPStatus
from flask import Flask, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)
flask_app = Flask(__name__)
CORS(flask_app)
CONFIG_FILE_URL = os.getenv(key="CONFIG_FILE_URL")
TG_AUTH_DATA = list()
TG_AUTH_API = None


def setup_config():
    global TG_AUTH_DATA
    global TG_AUTH_API
    if CONFIG_FILE_URL is None:
        logger.error("CONFIG_FILE_URL not provided")
        return
    try:
        logger.info("Downloading config file")
        config_file = requests.get(url=CONFIG_FILE_URL)
        if config_file.ok:
            logger.info("Loading config file data")
            if load_dotenv(stream=io.StringIO(config_file.content.decode()), override=True):
                logger.info("Parsing config data")
                TG_AUTH_DATA = json.loads(os.getenv(key="TG_AUTH_DATA"))
                for auth_data in TG_AUTH_DATA:
                    logger.info(f"Loaded token data for:: {auth_data['auth_data']['username']}")
                TG_AUTH_API = os.getenv(key='TG_AUTH_API')
        else:
            logger.error(f"Failed to download config file:: [{config_file.status_code} {config_file.reason}]")
    except UnicodeDecodeError:
        logger.error("Error occurred while decoding config file response")
    except KeyError:
        logger.error("Failed to read TG_AUTH_DATA")
    except json.JSONDecodeError:
        logger.error("Error occurred while parsing config data")
    except requests.exceptions.RequestException as err:
        logger.error(f"Failed to download config file:: {err.__class__.__name__}")


@flask_app.route('/')
def hello_msg():
    return jsonify({'msg': 'Hello from TG Token Service'}), HTTPStatus.OK


@flask_app.get('/token/<user_name>')
def fetch_token(user_name: str):
    logger.info(f"Received request to fetch token for:: {user_name}")
    token_data = None
    try:
        for tg_data in TG_AUTH_DATA:
            if user_name == tg_data['auth_data']['username']:
                token_data = tg_data
                logger.info(f"Loaded token req data for:: {user_name}")
                break
    except AttributeError:
        logger.error("TG_AUTH_DATA is not properly loaded")
        return jsonify({'msg': 'TG_AUTH_DATA is not properly loaded'}), HTTPStatus.INTERNAL_SERVER_ERROR
    if not token_data:
        logger.warning(f"Failed to find auth req data for:: {user_name}")
        return jsonify({'msg': 'Failed to find auth req data'}), HTTPStatus.BAD_REQUEST
    logger.info("Sending request to fetch token")
    try:
        req_body_str = json.dumps(token_data, separators=(",", ":"))
        req_headers = {
            "Content-Length": str(len(req_body_str)),
            "Content-Type": "application/json",
            "Origin": os.getenv(key='TG_ARCHIVE_URL'),
            "Referer": os.getenv(key='TG_ARCHIVE_URL')
        }
        auth_response = requests.post(url=TG_AUTH_API, data=json.dumps(token_data), headers=req_headers)
        if auth_response.ok:
            logger.info(f"Received response:: {auth_response.text}")
            return jsonify(json.loads(auth_response.content)), HTTPStatus.OK
        else:
            logger.error(f"Received failure response:: {auth_response.text}")
            return jsonify({'msg': 'Failed to get a valid token'}), HTTPStatus.FORBIDDEN
    except requests.exceptions.RequestException:
        error_msg = "Failed to get response from TG_AUTH_API"
        logger.error(error_msg)
    except json.JSONDecodeError:
        error_msg = "Json decode error while processing"
        logger.error(error_msg)
    return jsonify({'msg': error_msg})


setup_config()
