import requests
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
from common.log import logger
import re
# data = {
#     "message": " https://bohrium.dp.tech/paper/arxiv/2401.07868"
# }
#
# url = "http://47.253.33.28:10001/reply_wx"
# response = requests.post(url, json=data)
# result = response.text
# logger.info("[DP] result={}".format(result))
# following_text = result.replace('\\n', '')[:75]
# logger.info("[DP] wx——result={}".format(following_text))
#
# # pattern = r'arxiv/(\d+\.\d+)'
# # match = re.search(pattern, result)
# # if match:
# #     arxiv_id = match.group(1)
# #     print(f"Found arXiv ID: {arxiv_id}")
# # else:
# #     print("No match found")
# # arxiv_id = re.search(pattern, result).group(1)
# # pattern = r'\(https?://[^\s\)]+\)\s*(.*)'
# # following_text = re.search(pattern, result).group(1).replace('\\n', '')[:75]
# # # following_text = result[:100]
# # result = following_text+ "…… " + "点此查看全部解读：(https://bohrium.test.dp.tech/paper?session_id="  + "&arxiv_id=" + arxiv_id + ")"
# logger.info("[DP] wx——result={}".format(result))
wxurl = conf().get("wx-url")
logger.info("[DP] wx——result={}".format(wxurl))
