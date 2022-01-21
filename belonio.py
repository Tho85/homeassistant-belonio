"""Belonio API client"""
import asyncio
import logging
import socket
import json
import datetime

import aiohttp
import async_timeout

from typing import Any
from aiohttp import ClientError
from yarl import URL

from .const import AUTH_HOST, API_HOST

_LOGGER = logging.getLogger(__name__)

class Belonio:
    def __init__(
        self,
        websession: Any,
        username: str,
        password: str,
        access_token: str = None,
    ) -> None:
        self.websession = websession
        self._username = username
        self._password = password
        self._access_token = access_token
        self._timeout = 10
        self.user_info = None
        self.giftcards = None
        self.most_recent_giftcard = None

    async def fetch_user_info(self):
        """ Get user info. """
        response = await self._request(f"{API_HOST}/profiles/self")

        if response is None:
            return

        json_data = await response.json(content_type = "text/plain")
        if json_data is None:
            return

        self.user_info = json_data

    async def fetch_giftcards(self):
        """ Get user info. """
        if self.user_info is None:
            await self.fetch_user_info()

        params = { "employmentPublicId": self.current_employment_id() }
        response = await self._request(f"{API_HOST}/giftcards/search", body = params)

        if response is None:
            return

        json_data = await response.json()
        if json_data is None:
            return

        self.giftcards = json_data["content"]

    async def fetch_most_recent_giftcard(self):
        """ Get most recent giftcard """
        if self.giftcards is None:
            await self.fetch_giftcards()

        most_recent = sorted(self.giftcards, key=lambda x:-x["valuta"])[0]["giftcardId"]

        response = await self._request(f"{API_HOST}/giftcards/{most_recent}")

        if response is None:
            return

        json_data = await response.json()
        if json_data is None:
            return

        self.most_recent_giftcard = json_data

    def current_employment(self):
        if self.user_info is None:
            return None

        for k, v in self.user_info["employments"].items():
            if v["validTill"] is None:
                return v

        return None

    def current_employer(self):
        if self.current_employment() is None:
            return None

        self.current_employment()["employer"]["name"]

    def current_employment_id(self):
        if self.current_employment is None:
            return None

        return self.current_employment()["publicId"]


    async def login(self):
        """ Try to login """
        self._access_token = await get_belonio_token(
            self.websession, self._username, self._password
        )

        return self._access_token != None

    async def _request(self, url, body=None, retry=3):
        self._prev_request = datetime.datetime.utcnow()
        _LOGGER.debug("Request %s %s %s", url, retry, body)

        if self._access_token is None:
            _LOGGER.debug("Fetching token")
            await self.login()

            if self._access_token is None:
                return None

        _LOGGER.debug("Token received: %s", self._access_token)

        headers = {
            "Authorization": f"Bearer {self._access_token}",
        }

        try:
            async with async_timeout.timeout(self._timeout):
                if body:
                    response = await self.websession.post(
                        url, json = body, headers = headers
                    )
                else:
                    response = await self.websession.get(
                        url, headers = headers
                    )

            r = await response.text()
            _LOGGER.debug(
                "response: %s %s %s",
                response.status,
                response.reason,
                r,
            )

            if response.status > 400:
                self._access_token = None

                if retry > 0:
                    if response.status == 429:
                        _LOGGER.warning("Too many requests")
                        return None

                    return await self._request(url, body, retry = retry - 1)

                _LOGGER.error(
                    "Error connecting to Belonio, response: %s %s",
                    response.status,
                    response.reason,
                )

                return None

        except ClientError as err:
            self._access_token = None
            if retry > 0 and "429" not in str(err):
                return await self._request(url, body, retry=retry - 1)

            _LOGGER.error("Error connecting to Belonio: %s ", err, exc_info=True)
            raise

        except asyncio.TimeoutError:
            self._access_token = None
            if retry > 0:
                return await self._request(url, body, retry=retry - 1)

            _LOGGER.error("Timed out when connecting to Belonio")
            raise

        self._prev_request = datetime.datetime.utcnow()

        _LOGGER.debug(
            "returning response: %s %s",
            response.status,
            response.reason,
        )

        return response


async def get_belonio_token(
    websession: Any,
    username: str,
    password: str,
    retry=3,
    timeout=30,
    ):
        try:
            async with async_timeout.timeout(timeout):
                response = await websession.post(
                    f"{AUTH_HOST}/token",
                    headers = {
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Accept": "application/json",
                    },
                    data = {
                        "grant_type": "password",
                        "username": username,
                        "password": password,
                        "scope": "openid profile email offline_access",
                        "client_id": "login.belonio.app",
                    },
                )
        except ClientError as err:
            if retry > 0:
                return await get_belonio_token(
                    websession, username, password, retry = retry - 1
                )
            _LOGGER.error("Error getting token Belonio: %s", err, exc_info = True)
            return None
        except asyncio.TimeoutError:
            if retry > 0:
                return await get_belonio_token(
                    websession, username, password, retry = retry - 1
                )
            _LOGGER.error("Timeout getting token Belonio: %s", err, exc_info = True)
            return None

        if response.status != 200:
            _LOGGER.error(
                "Belonio: Failed to get token: %s %s",
                response.status,
                response.reason,
            )
            return None

        token_data = json.loads(await response.text())
        return token_data.get("access_token")
