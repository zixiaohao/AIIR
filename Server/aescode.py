#!/usr/bin/env python
# -*- coding: utf-8 -*-

import base64
import json
from Crypto.Cipher import AES


class AESCoder(object):
    def __init__(self):
        self.__encryptKey = 'p8FNKkLcaZf6GdaRXCij705HvwEyOPLr'
        self.__key = base64.b64decode(self.__encryptKey)

    def encrypt(self, data):
        """
        ECB模式加密
        :param data:
        :return:
        """
        BS = 16
        pad = lambda s: s + (BS - len(s) % BS) * chr(BS - len(s) % BS)
        cipher = AES.new(self.__key, AES.MODE_ECB)
        encrData = cipher.encrypt(pad(data).encode())
        encrData = base64.b64encode(encrData)
        return encrData

    def decrypt(self, encrData):
        """
        ECB模式解密
        :param encrData:
        :return:
        """
        encrData = base64.b64decode(encrData)
        # unpad = lambda s: s[0:-s[len(s)-1]]
        unpad = lambda s: s[0:-s[-1]]
        cipher = AES.new(self.__key, AES.MODE_ECB)
        decrData = unpad(cipher.decrypt(encrData))
        return decrData.decode('utf-8')


if __name__ == '__main__':
    aes = AESCoder()
