import requests
from common.log import logger
import re
data = {
    "message": "https://arxiv.org/abs/2405.20347"
}

url = "http://47.253.33.28:10001/reply_wx"
response = requests.post(url, json=data)
result = response.text
logger.info("[DP] result={}".format(result))



pattern = r'arxiv/(\d+\.\d+)'
arxiv_id = re.search(pattern, result).group(1)
pattern = r'\(https?://[^\s\)]+\)\s*(.*)'
# following_text = re.search(pattern, result).group(1).replace('\\n', '')[:75]
following_text = result[:100]
result = following_text+ "…… " + "点此查看全部解读：(https://bohrium.test.dp.tech/paper?session_id="  + "&arxiv_id=" + arxiv_id + ")"
logger.info("[DP] wx——result={}".format(result))

