import json
import requests
import settings
import ssl
from scpi_logger import logger
from settings import BASE_URL, COMMON_SETTINGS


class Requester(object):

    def __init__(self, *args, **kwargs):
        self.auth_token = str(settings.AUTH_TOKEN)
        self.session = requests.session()
        self.session.headers.update(self.get_default_headers())
        self.request_dict = {
            'get': requests.get,
            'post': requests.post,
            'put': requests.put,
            'del': requests.delete,
        }

    def get_default_headers(self, refresh=False):
        """Gets the headers for a request

        Summary:
            Assigns the auth token to the Auth-Token header.
            If a refresh is needed, a request is made with the
            refresh token and the auth token is updated.

        Paramters:
            refresh: a boolean to trigger refreshes

        Returns:
            a dictionary with the Auth-Token header

        """
        if refresh and 'REFRESH_TOKEN' in COMMON_SETTINGS:
            url = BASE_URL + '/profile/auth_token/refresh'
            headers = {'Refresh-Token': COMMON_SETTINGS['REFRESH_TOKEN']}
            try:
                response = requests.get(url, headers=headers)
                assert response.status_code == 200
            except Exception:
                logger.warning("Unable to get refresh token", exc_info=True)
            data = json.loads(response.text)
            try:
                self.auth_token = data['new auth token']
            except KeyError:
                logger.warning("No new auth token in response")
        headers = {
            'Auth-Token': self.auth_token,
            'Content-Type': 'application/json',
            'Accept': 'text/plain',
        }
        return headers

    def https_get(self, url, params={}, headers={}):
        return self.https_request(url, params=params, kind='get',
                                  headers=headers)

    def https_post(self, url, data, headers={}):
        return self.https_request(url, data=data, kind='post', headers=headers)

    def https_request(self, url, data={}, params={}, headers={},
                      kind='get'):
        """Makes https requests

        Summary:
            Tries to make a https request and logs exceptions.
            Will retry the

        Parameters:
            url: the target url
            data: a dictionary payload for POST or PUT requests
            params: a dictionary of params for GET or DEL requests
            headers: request headers, these will update the base
                headers that are already assigned by get_default_headers
            kind: the flavor of the request (GET, POST, etc.)

        Returs:
            a requests module response object
        """
        hdrs = self.get_default_headers()
        hdrs.update(headers)

        response = None
        try:
            if data:
                response = self.request_dict[kind](url, data=data, headers=hdrs)
            else:
                response = self.request_dict[kind](url, params=params, headers=hdrs)
        except ssl.SSLError:
            logger.warning("SSLError!", exc_info=True)
            logger.info("Retrying request to {}".format(url))
            response = self._retry_request(url, kind, data, params, headers)
        except Exception as e:
            logger.warning("Unexpected request exc: {}".format(e))
            logger.debug("The request exception info:", exc_info=True)

        if not response:
            logger.warning("No response from {}".format(url))
        elif response.status_code in [401, 403]:
            # refresh headers and try again
            hdrs = self.get_default_headers(refresh=True)
            self.session.headers.update(hdrs)
            response = self._retry_request(url, kind, data, params,
                                           headers)
        elif response.status_code != 200:
            self._log_http_err_response(response, data, params)

        # reset the headers to default
        self.session.headers = self.get_default_headers()
        return response

    def _retry_request(self, url, kind, data={}, params={}, headers={}):
        """Retries the https request with a fresh session"""
        self.session = requests.session()
        self.session.headers.update(self.get_default_headers())
        response = None
        if headers:
            # include any headers from method arg
            self.session.headers.update(headers)
        try:
            if data:
                response = self.request_dict[kind](url, data=data)
            else:
                response = self.request_dict[kind](url, params=params)
        except ssl.SSLError:
            logger.warning("SSLError on retry. Aborting request.")
        except Exception as e:
            logger.warning("The retry request encountered an unexpected "
                           "exception: {}".format(e))
            logger.debug("The retry request exception info:", exc_info=True)
        return response

    def _log_http_err_response(self, response, data={}, params={}):
        logger.warning("response.text %s" % response.text)
        logger.warning("request headers %s" % self.session.headers)
        logger.warning("more request details in debug level")
        if data:
            msg = "request data %s" % data
        elif params:
            msg = "request params %s" % params
        if len(msg) > 500:
            msg = msg[0:500] + "..."
        logger.debug(msg)
