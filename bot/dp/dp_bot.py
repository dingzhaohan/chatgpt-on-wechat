# encoding:utf-8

import time
import uuid

import openai
import openai.error
import requests

from bot.bot import Bot
from bot.dp.dp_session import DPSession
from bot.openai.open_ai_image import OpenAIImage
from bot.session_manager import SessionManager
from bridge.context import ContextType
from bridge.reply import Reply, ReplyType
from common.log import logger
from common.token_bucket import TokenBucket
from config import conf, load_config

chat_url = 'https://chatbohr.test.dp.tech/'

# OpenAI对话模型API (可用)
class DPBot(Bot, OpenAIImage):
    def __init__(self):
        super().__init__()
        openai.api_key = "sk-e7W5DteJzLagdIXR4743B34b8b374c3fA154F6A3B5B11a9a"
        openai.api_base = "http://39.101.164.143:50001/v1"
        self.sessions = SessionManager(DPSession, model=conf().get("model") or "gpt-3.5-turbo")
        self.args = {
            "model": conf().get("model") or "gpt-3.5-turbo",  # 对话模型的名称
            "temperature": conf().get("temperature", 0.9),  # 值在[0,1]之间，越大表示回复越具有不确定性
            # "max_tokens":4096,  # 回复最大的字符数
            "top_p": conf().get("top_p", 1),
            "frequency_penalty": conf().get("frequency_penalty", 0.0),  # [-2,2]之间，该值越大则更倾向于产生不同的内容
            "presence_penalty": conf().get("presence_penalty", 0.0),  # [-2,2]之间，该值越大则更倾向于产生不同的内容
            "request_timeout": conf().get("request_timeout", None),  # 请求超时时间，openai接口默认设置为600，对于难问题一般需要较长时间
            "timeout": conf().get("request_timeout", None),  # 重试超时时间，在这个时间内，将会自动重试
        }

    def reply(self, query, context=None):
        # acquire reply content
        if context.type == ContextType.TEXT:
            logger.info("[DP] query={}".format(query))

            session_id = context["session_id"]
            reply = None
            clear_memory_commands = conf().get("clear_memory_commands", ["#清除记忆"])
            if query in clear_memory_commands:
                self.sessions.clear_session(session_id)
                reply = Reply(ReplyType.INFO, "记忆已清除")
            elif query == "#清除所有":
                self.sessions.clear_all_session()
                reply = Reply(ReplyType.INFO, "所有人记忆已清除")
            elif query == "*更新配置":
                load_config()
                reply = Reply(ReplyType.INFO, "配置已更新")
            if reply:
                return reply
            session = self.sessions.session_query(query, session_id)
            logger.debug("[CHATGPT] session query={}".format(session.messages))

            api_key = context.get("openai_api_key")
            model = context.get("gpt_model")
            new_args = None
            if model:
                new_args = self.args.copy()
                new_args["model"] = model
            # if context.get('stream'):
            #     # reply in stream
            #     return self.reply_text_stream(query, new_query, session_id)

            reply_content = self.reply_text(session, api_key, args=new_args)
            logger.debug(
                "[CHATGPT] new_query={}, session_id={}, reply_cont={}, completion_tokens={}".format(
                    session.messages,
                    session_id,
                    reply_content["content"],
                    reply_content["completion_tokens"],
                )
            )
            if reply_content["completion_tokens"] == 0 and len(reply_content["content"]) > 0:
                reply = Reply(ReplyType.ERROR, reply_content["content"])
            elif reply_content["completion_tokens"] > 0:
                self.sessions.session_reply(reply_content["content"], session_id, reply_content["total_tokens"])
                reply = Reply(ReplyType.TEXT, reply_content["content"])
            else:
                reply = Reply(ReplyType.ERROR, reply_content["content"])
                logger.debug("[CHATGPT] reply {} used 0 tokens.".format(reply_content))
            return reply

        elif context.type == ContextType.IMAGE_CREATE:
            ok, retstring = self.create_img(query, 0)
            reply = None
            if ok:
                reply = Reply(ReplyType.IMAGE_URL, retstring)
            else:
                reply = Reply(ReplyType.ERROR, retstring)
            return reply
        else:
            reply = Reply(ReplyType.ERROR, "Bot不支持处理{}类型的消息".format(context.type))
            return reply

    def reply_text(self, session: DPSession, api_key=None, args=None, retry_count=0) -> dict:
        """
        call openai's ChatCompletion to get the answer
        :param session: a conversation session
        :param session_id: session id
        :param retry_count: retry count
        :return: {}
        """
        try:
            if conf().get("rate_limit_chatgpt") and not self.tb4chatgpt.get_token():
                raise openai.error.RateLimitError("RateLimitError: rate limit exceeded")
            # if api_key == None, the default openai.api_key will be used
            if args is None:
                args = self.args
            if "https:" in session.messages[-1]["content"]:     
                import requests
                import re
                data = {
                    "message": session.messages[-1]["content"]
                }

                url = "http://47.253.33.28:10001/reply_wx"
                response = requests.post(url, json=data)
                result = response.text
                logger.info("[DP] result={}".format(result))
                create_session_url = chat_url + "api/v1/session/create"
                create_session_data = {
                    "arxiv_id": "",
                    "all_text": "",
                    "pdf_url": ""
                }
                create_session_response = requests.post(create_session_url, json=create_session_data)
                session_id = create_session_response.json()["session_id"]
                logger.info("[DP] session_id={}".format(session_id))
                add_url = chat_url + "api/v1/session/add"
                add_user_data = {
                    "session_id": session_id,
                    "role": "user",
                    "content": session.messages[-1]["content"]
                }
                requests.post(add_url, json=add_user_data)

                add_system_data = {
                    "session_id": session_id,
                    "role": "system",
                    "content": result
                }

                requests.post(add_url, json=add_system_data)

                # 匹配链接及其后面的文本
                pattern = r'\(https?://[^\s\)]+\)\s*(.*)'
                match = re.search(pattern, result)
                if match :
                    following_text = match.group(1).replace('\\n', '')[:75]
                else:
                    following_text = result.replace('\\n', '')[:75]

                result = following_text + "…… " + "点此查看全部解读：(https://bohrium-square.test.dp.tech/paper/landing?sessionId=" + session_id +")"
                logger.info("[DP] wx-result={}".format(result))


                # if "https:" in result:
                #     pattern = r'arxiv/(\d+\.\d+)'
                #     arxiv_id = re.search(pattern, result).group(1)
                #     logger.info("[DP] arxiv_id={}".format(arxiv_id))
                #
                #     create_session_url = chat_url + "api/v1/session/create"
                #     create_session_data = {
                #         "arxiv_id": arxiv_id,
                #         "all_text": "",
                #         "pdf_url":  ""
                #     }
                #     create_session_response = requests.post(create_session_url,json=create_session_data)
                #     session_id = create_session_response.json()["session_id"]
                #     logger.info("[DP] session_id={}".format(session_id))
                #     add_url = chat_url + "api/v1/session/add"
                #     add_user_data = {
                #         "session_id": session_id,
                #         "role": "user",
                #         "content": session.messages[-1]["content"]
                #     }
                #     requests.post(add_url, json=add_user_data)
                #
                #
                #     add_system_data = {
                #         "session_id": session_id,
                #         "role": "system",
                #         "content": result
                #     }
                #
                #     requests.post(add_url, json=add_system_data)
                #
                #
                #     # 匹配链接及其后面的文本
                #     pattern = r'\(https?://[^\s\)]+\)\s*(.*)'
                #     match = re.search(pattern, result)
                #
                #     following_text = match.group(1).replace('\\n', '')[:75]
                #
                #
                #     result = following_text+ "…… " + "点此查看全部解读：(https://bohrium.test.dp.tech/paper/landing?sessionId=" + session_id + "&arxivId=" + arxiv_id + ")"
                #     logger.info("[DP] wx-result={}".format(result))
                # elif  "https://bohrium.dp.tech/paper/arxiv" in session.messages[-1]["content"]:
                #     pattern = r'arxiv/(\d+\.\d+)'
                #     arxiv_id = re.search(pattern, session.messages[-1]["content"]).group(1)
                #     logger.info("[DP] arxiv_id={}".format(arxiv_id))
                #
                #     create_session_url = chat_url + "api/v1/session/create"
                #     create_session_data = {
                #         "arxiv_id": arxiv_id,
                #         "all_text": "",
                #         "pdf_url": ""
                #     }
                #     create_session_response = requests.post(create_session_url, json=create_session_data)
                #     session_id = create_session_response.json()["session_id"]
                #     logger.info("[DP] session_id={}".format(session_id))
                #     add_url = chat_url + "api/v1/session/add"
                #     add_user_data = {
                #         "session_id": session_id,
                #         "role": "user",
                #         "content": session.messages[-1]["content"]
                #     }
                #     requests.post(add_url, json=add_user_data)
                #
                #     add_system_data = {
                #         "session_id": session_id,
                #         "role": "system",
                #         "content": result
                #     }
                #
                #     requests.post(add_url, json=add_system_data)
                #
                #
                #     following_text = result[:75]
                #
                #     result = following_text + "…… " + "点此查看全部解读：(https://bohrium.test.dp.tech/paper/landing?sessionId=" + session_id + "&arxivId=" + arxiv_id + ")"
                #     logger.info("[DP] wx-result={}".format(result))
                #

                return {
                    "total_tokens": 1000,
                    "completion_tokens": 1000,
                    "content": result
                }
            openai.api_key = "sk-e7W5DteJzLagdIXR4743B34b8b374c3fA154F6A3B5B11a9a"
            openai.api_base = "http://39.101.164.143:50001/v1"
            response = openai.ChatCompletion.create(model="qwen-plus", messages=session.messages)
            # logger.debug("[CHATGPT] response={}".format(response))
            # logger.info("[ChatGPT] reply={}, total_tokens={}".format(response.choices[0]['message']['content'], response["usage"]["total_tokens"]))
            return {
                "total_tokens": response["usage"]["total_tokens"],
                "completion_tokens": response["usage"]["completion_tokens"],
                "content": response.choices[0]["message"]["content"],
            }
        except Exception as e:
            need_retry = retry_count < 2
            result = {"completion_tokens": 0, "content": "我现在有点累了，等会再来吧"}
            if isinstance(e, openai.error.RateLimitError):
                logger.warn("[CHATGPT] RateLimitError: {}".format(e))
                result["content"] = "提问太快啦，请休息一下再问我吧"
                if need_retry:
                    time.sleep(20)
            elif isinstance(e, openai.error.Timeout):
                logger.warn("[CHATGPT] Timeout: {}".format(e))
                result["content"] = "我没有收到你的消息"
                if need_retry:
                    time.sleep(5)
            elif isinstance(e, openai.error.APIError):
                logger.warn("[CHATGPT] Bad Gateway: {}".format(e))
                result["content"] = "请再问我一次"
                if need_retry:
                    time.sleep(10)
            elif isinstance(e, openai.error.APIConnectionError):
                logger.warn("[CHATGPT] APIConnectionError: {}".format(e))
                result["content"] = "我连接不到你的网络"
                if need_retry:
                    time.sleep(5)
            else:
                logger.exception("[CHATGPT] Exception: {}".format(e))
                need_retry = False
                self.sessions.clear_session(session.session_id)

            if need_retry:
                logger.warn("[CHATGPT] 第{}次重试".format(retry_count + 1))
                return self.reply_text(session, api_key, args, retry_count + 1)
            else:
                return result

