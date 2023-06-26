# Copyright (c) 2018-2019, The Linux Foundation. All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met:
#    * Redistributions of source code must retain the above copyright
#      notice, this list of conditions and the following disclaimer.
#    * Redistributions in binary form must reproduce the above
#      copyright notice, this list of conditions and the following
#      disclaimer in the documentation and/or other materials provided
#      with the distribution.
#    * Neither the name of The Linux Foundation nor the names of its
#      contributors may be used to endorse or promote products derived
#      from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY EXPRESS OR IMPLIED
# WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NON-INFRINGEMENT
# ARE DISCLAIMED.  IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS
# BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR
# BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE
# OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN
# IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

"""
This module provides APIs for communicating with QMMF IPC webserver.
"""

import aiohttp
import logging
import traceback

# Port over which the camera/QMMF IPC webserver
IPC_WEBSERVER_PORT = "1080"
LOGIN_PATH = "login"
LOGOUT_PATH = "logout"
POST_METHOD = "post"
GET_METHOD = "get"
ALL_METHODS = [POST_METHOD, GET_METHOD]


class IpcProvider():
    """
    This class provides interface to QMMF IPC webserver.

    Attributes
    ----------
    username : str
        username of the camera.
    password : str
        password of the camera.
    ip_address : str
        IP address of the camera.

    """

    def __init__(self, ip, username=None, password=None):
        """
        This is the constructor for `IpcProvider` class

        """
        self.username = username
        self.password = password
        self.ip_address = ip
        self.host = ":".join([ip, str(IPC_WEBSERVER_PORT)])

        #: str: Session identifier obtained from the
        #:      camera/QMMF IPC webserver .
        self._session_token = None
        self._heartbeat_manager = None
        self.logger = logging.getLogger("iotccsdk")

    def _show_error(self, err_msg):
        """
        Private method for logging error messages.

        Parameters
        ----------
        err_msg : str
            Error message to be logged.

        """
        self.logger.error(err_msg)

    def _get_function_name(self):
        """
        Private method for getting function name.

        Returns
        -------
            Function name from which it is called.

        """
        return traceback.extract_stack(None, 2)[0][2]

    def _build_url(self, api_path):
        """
        Private method for constructing request url.

        Parameters
        ----------
        api_path : str
            api portion of the path in list:
            ["login", "logout", "video", "preview", vam",
             "recording", "overlayconfig", "overlay", "captureimage"]
        Returns
        -------
        str
            Constructed request url
        """
        base_address = "".join(["http://", self.host])
        return "/".join([base_address, api_path.strip("/")])

    async def get(self, path, payload=None, param=None):
        """
        GET API for QMMF IPC webserver.

        Parameters
        ----------
        path : str
            QMMF IPC webserver API.
        payload : dict
            Key value pairs for `path` API
        param : str
            Params for the `path` API.

        Returns
        -------
        response: dict
            response from the GET call

        Raises
        ------
        ConnectionError
            When response is malformed
        Exception
            Any exception that occurs during the request.
        """

        return await self.__send_request(GET_METHOD, path, payload, param)

    async def post(self, path, payload=None, param=None):
        """
        POST API for QMMF IPC webserver.

        Parameters
        ----------
        path : str
            QMMF IPC webserver API.
        payload : dict
            Key value pairs for `path` API
        param : str
            Params for the `path` API.

        Returns
        -------
        response: dict
            response from the POST call

        Raises
        ------
        Exception
            Any exception that occurs during the request.
        ConnectionError
            When response is malformed
        """

        return await self.__send_request(POST_METHOD, path, payload, param)

    async def __send_request(self, method, path, payload, params):
        """
        private method to send requests to QMMF IPC webserver.

        Parameters
        ----------
        method : str
            Method type for call must be in `ALL_METHODS`
        path : str
            QMMF IPC webserver API.
        payload : str
            JSON payload for the `path` API.
        params : str
            Params for the `path` API.

        Returns
        -------
        response: dict
            response from the request

        Raises
        ------
        ConnectionError
            When response is malformed
        Exception
            Any exception that occurs during the request.

        """

        if (method.lower() not in ALL_METHODS):
            raise ValueError("Method must be in %s" % ALL_METHODS)

        url = self._build_url(path)
        headers = {"Cookie": self._session_token}
        self.logger.info("API: %s data %s" % (url, payload))
        try:
            async with aiohttp.ClientSession() as mysession:
                response: aiohttp.ClientResponse
                async with mysession.request(method.lower(), url, json=payload, headers=headers, params=params) as response:
                    if response.ok:
                        self.logger.info("RESPONSE: %s" % response.text)

                    result = await response.json()
                    if "status" not in result and "Status" not in result:
                        raise ConnectionError(
                            f"Call with method: {method} to: {url} returned malformed response: {response}")
            return result
        except Exception as e:
            self.logger.exception(e)
            raise

    async def connect(self):
        """
        Establish a connection with QMMF IPC webserver on the camera.

        This API also sets the `session_token` attribute from the token
        obtained from the camera.

        Returns
        -------
        bool
            True if the connection was successful.

        Raises
        ------
        ConnectionError
            When the result of the call is a failure
        Timeout
            When the request times out on the connect request.
        RequestException
            The request is not correctly formed.

        """
        if self._session_token:
            # This is to clear out previous session before starting a new one
            await self.logout()

        async with aiohttp.ClientSession() as mysession:
            try:
                url = self._build_url(LOGIN_PATH)
                payload = {"username": self.username, "userpwd": self.password}
                self.logger.info("API: %s data: %s" % (url, payload))
                async with mysession.post(url, json=payload) as response:
                    self.logger.info("Login response: %s" % response.text)
                    result = await response.json()
                    if "status" in result and result["status"]:
                        self._session_token = response.headers["Set-Cookie"]
                        self.logger.info(
                            "connection established with session token: [%s]" % self._session_token)
                        self._heartbeat_manager = HeartBeatManager(mysession)
                        return True
                    else:
                        raise ConnectionError(
                            "Failed to connect. Server returned status=False")
            except Exception as e:
                self.logger.exception(e)
                raise

    async def logout(self):
        """
        Logout from the QMMF IPC webserver on the camera.

        Returns
        -------
        bool
            True if the logout was successful.
            False on failure.

        Raises
        ------
        Exception
            Any exception that occurs during the request.

        """
        try:
            if self._heartbeat_manager:
                self._heartbeat_manager.stop()
            response = await self.post(LOGOUT_PATH)
            if "status" in response and response["status"]:
                return response["status"]
            else:
                return False
        except Exception as e:
            self.logger.exception(e)
            raise


class HeartBeatManager():
    def __init__(self, host: str):
        self.logger = logging.getLogger("iotccsdk")
        self.uri = f"ws://{host}/async"
        self._ws = None

    async def on_message(self, message):
        self.logger.debug(message)

    async def on_error(self):
        self.logger.error("IPC Websocket error!")

    async def on_open(self):
        self.logger.info("Starting heartbeat...")

    async def run(self, session: aiohttp.ClientSession = None):
        self.logger.info(f"Connecting to: {self.uri}")
        # self._ws.run_forever(ping_interval=11, ping_timeout=10)
        async with session.ws_connect(self.uri) as ws:
            self._ws = ws
            await self.on_open()
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    await self.on_message(msg.data)
                elif msg.type == aiohttp.WSMsgType.CLOSED:
                    await ws.close()
                    break
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    await self.on_error()
                    break

    def stop(self):
        self.logger.info("Stopping heartbeat...")
        if self._ws:
            self._ws.close()
