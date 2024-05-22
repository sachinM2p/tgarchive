import os
import io
import json
import logging
import requests
from http import HTTPStatus
from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv
from typing import Optional

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)
flask_app = Flask(__name__)
CORS(flask_app)
CONFIG_FILE_URL = os.getenv(key="CONFIG_FILE_URL")
TG_AUTH_DATA = list()
TG_AUTH_API: Optional[str] = None
TG_SEARCH_API: Optional[str] = None


def setup_config():
    global TG_AUTH_DATA
    global TG_AUTH_API
    global TG_SEARCH_API
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
                TG_SEARCH_API = os.getenv(key='TG_SEARCH_API')
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


@flask_app.post("/search")
def search_files():
    logger.info(f"Received request to search with data:: {request.get_data(as_text=True, cache=False)}")
    logger.info(f"Sending request to:: {TG_SEARCH_API}")
    try:
        req_headers = {
            "Authorization": request.headers.get('Authorization'),
            "Content-Length": str(request.headers.get('Content-Length')),
            "Content-Type": "text/plain;charset=UTF-8",
            "Origin": os.getenv(key='TG_ARCHIVE_URL'),
            "Referer": os.getenv(key='TG_ARCHIVE_URL')
        }
        response = requests.post(url=TG_SEARCH_API, data=json.dumps(request.get_data(cache=False, as_text=False)),
                                 headers=req_headers, timeout=5)
        logger.info(f"Received response with status:: {response.status_code} {response.reason}")
        return jsonify(json.loads(response.content)), HTTPStatus.OK if response.ok else HTTPStatus.BAD_REQUEST
    except KeyError:
        err_msg = "Invalid request data received"
        logger.error(err_msg)
    except json.JSONDecodeError:
        err_msg = "Failed to parse json data"
        logger.error(err_msg)
    except requests.exceptions.RequestException as err:
        err_msg = f"Failed to search:: {err.__class__.__name__}"
        logger.error(err_msg)
    return jsonify({'msg': err_msg}), HTTPStatus.INTERNAL_SERVER_ERROR


setup_config()
