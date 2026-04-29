#!/usr/bin/env python
# -*- coding: utf-8 -*-

import base64
import json
import os
from Crypto.Cipher import AES


class AESCoder(object):
    def __init__(self):
        self.__encryptKey = os.environ.get('AIIR_AES_KEY', '')
        if not self.__encryptKey:
            raise ValueError(
                "AES密钥未配置。请设置环境变量 AIIR_AES_KEY（Base64编码的32字节密钥）。"
                "示例: export AIIR_AES_KEY='your_base64_encoded_32byte_key'"
            )
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
    import sys
    if len(sys.argv) < 2:
        print("用法:")
        print("  加密: python aescode.py encrypt <明文>")
        print("  解密: python aescode.py decrypt <密文>")
        print("  生成密钥: python aescode.py genkey")
        print()
        print("环境变量 AIIR_AES_KEY 必须已设置。")
        sys.exit(1)

    action = sys.argv[1]
    aes = AESCoder()

    if action == 'encrypt':
        result = aes.encrypt(sys.argv[2])
        print(f"密文: {result.decode()}")
    elif action == 'decrypt':
        result = aes.decrypt(sys.argv[2])
        print(f"明文: {result}")
    elif action == 'genkey':
        import secrets
        key = base64.b64encode(secrets.token_bytes(32)).decode()
        print(f"生成的AES密钥: {key}")
        print("请设置环境变量: export AIIR_AES_KEY='{}'".format(key))
