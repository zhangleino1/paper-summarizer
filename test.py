import requests
import re
from bs4 import BeautifulSoup
import logging
headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
        'cookie': 'HSID=A_DD98WEIxsZsZc1D; SSID=Acev8bMzZMZ-CHBqd; APISID=ol9iD2CnHWFkjR6A/AphA9fyLgdows48j1; SAPISID=bAFbrV_vxE88zUON/AAEQDZY3Ih52DjQC5; __Secure-1PAPISID=bAFbrV_vxE88zUON/AAEQDZY3Ih52DjQC5; __Secure-3PAPISID=bAFbrV_vxE88zUON/AAEQDZY3Ih52DjQC5; GSP=LM=1713536331:S=Ht2EeIZJY6yo2fZm; SEARCH_SAMESITE=CgQI15sB; SID=g.a000mgg5DJ-LGRng_4NuGlwwJt7hy3rrcY8qMQEuphLK51otZLugCQoRX_ZOGhvP7J3Rn96EYgACgYKAc4SARUSFQHGX2MihSJ1TjKlro8BtaQxUFPIFRoVAUF8yKpQEdi69tnxJWObbNCwGRwP0076; __Secure-1PSID=g.a000mgg5DJ-LGRng_4NuGlwwJt7hy3rrcY8qMQEuphLK51otZLugDJa2sr68sT5C5rIL9Y-7awACgYKAdoSARUSFQHGX2MiNg8zEzovcDHkdr4cgF3spBoVAUF8yKoYKdFZNXJBOE27-ktp_7pG0076; __Secure-3PSID=g.a000mgg5DJ-LGRng_4NuGlwwJt7hy3rrcY8qMQEuphLK51otZLugtlCOMMTsX_xLmhJoO9xZBQACgYKAQASARUSFQHGX2MiKvDoa4FyklqtfomMLEWNbRoVAUF8yKo2QJIh6OtPUA33Y1tEMo2J0076; OGPC=19026797-10:19026792-1:; AEC=AVYB7crBKOo4i964_5eZ8CCIJaZF8UWX2_LOibVbtHdFs1_KiLwhwYHHkVY; mp_851392464b60e8cc1948a193642f793b_mixpanel=%7B%22distinct_id%22%3A%20%22%24device%3A191a8b2019c54c-033061441b06e-26001051-1fa400-191a8b2019c54c%22%2C%22%24device_id%22%3A%20%22191a8b2019c54c-033061441b06e-26001051-1fa400-191a8b2019c54c%22%2C%22%24initial_referrer%22%3A%20%22%24direct%22%2C%22%24initial_referring_domain%22%3A%20%22%24direct%22%2C%22%24search_engine%22%3A%20%22google%22%7D; NID=517=AoAMxNP9bhSOqgEQcSGFD0iIr4iD7bakt1iS_O7k2vVCTQbQRIRoPv-xfmnti1Tbkol0XPIymFXqnGQfjaABZS4AO5NLHvc1jbfO1f1W9J8SGe-S09L8XeOb4gWwmc7bGzqTdciYNbr-s4qtE8u19kORMTZpF83CJ4K76QTRnO4r5gD1y9FAGBiuZU3BEAAsZ4vSD_65XsURB0menj3fT7f6SL1T3dpKGMs3CYcvHTGeNpmg28cZcBoy9lSLpL_DgUqANemzSH0M0122OcOxZQDbnyzvIbJFwjxfDZvHu_JmsAXhkaV3CvFWchEuoQwVeI4KD00I7BECid1jK0t3kfKJmoK-Krs5pwnjH5tlBQc1S9wch63iwRaHuWw; __Secure-1PSIDTS=sidts-CjIBUFGoh9Vky5sr-opqPumhtnS-qvPlJFg6tNH4gHNEwhLXNPFy6ZOBv1BvVcg2tA4TMhAA; __Secure-3PSIDTS=sidts-CjIBUFGoh9Vky5sr-opqPumhtnS-qvPlJFg6tNH4gHNEwhLXNPFy6ZOBv1BvVcg2tA4TMhAA; SIDCC=AKEyXzUDbTwWHUL1HgPSCPqT3ihD2tCB7i1sz_7v6U2AEAitv3NKQ9yPXIaABW_z_Qlp-oWnL8s; __Secure-1PSIDCC=AKEyXzXKYtFYJ65HpUdHecxScdqtX5_GESv0JgFUDc5TZxlQPbwk2eQpEAqFR4YCzRiJNKuSpBmE; __Secure-3PSIDCC=AKEyXzUlsC7gD9jgjrS4U7iYLyfwUxySJJIbZRMSsdodrW830O7SMg8uKnawUmh0ycg_lmnhaRk',
        'priority': 'u=0, i',
        'sec-ch-ua': '"Not=A?Brand";v="8", "Chromium";v="129", "Google Chrome";v="129"',
        'sec-ch-ua-arch': '"x86"',
        'sec-ch-ua-bitness': '"64"',
        'sec-ch-ua-full-version-list': '"Not=A?Brand";v="8.0.0.0", "Chromium";v="129.0.6668.12", "Google Chrome";v="129.0.6668.12"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-model': '""',
        'sec-ch-ua-platform': '"Windows"',
        'sec-ch-ua-platform-version': '"19.0.0"',
        'sec-ch-ua-wow64': '?0',
        'sec-fetch-dest': 'document',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-site': 'none',
        'sec-fetch-user': '?1',
        'upgrade-insecure-requests': '1',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36'
    }

def get_final_url(url):
    try:
        response = requests.get(url, headers=headers,allow_redirects=True)
        # 解析返回的HTML
        soup = BeautifulSoup(response.content, 'html.parser')

        # 尝试找到 <script> 标签并解析其中的 location.replace 链接
        script_tag = soup.find('script', text=re.compile(r'location\.replace'))
        if script_tag:
            match = re.search(r'location\.replace\([\'"](.+?)[\'"]\)', script_tag.string)
            if match:
                final_url = match.group(1)
                return final_url

        # 如果没有 <script> 标签的情况，直接返回重定向后的URL
        return response.url
    except requests.RequestException as e:
        logging.error(f"Error resolving final URL for {url}: {e}")
        return None
    

if __name__ == '__main__':
    url = 'https://scholar.google.com.hk/scholar_url?url=https://neiudc.neiu.edu/cgi/viewcontent.cgi%3Farticle%3D1052%26context%3Duhp-projects&hl=zh-CN&sa=X&d459402106827766028&ei=vHvSZunGDLSp6rQPttzJMQ&scisigWwaebmvDzaa7t8L0_nbwdXs59u&oi=scholaralrt&hist=OQwY7CMAAAAJ:14835400406247003880:AFWwaebQoA48R89JX59T7cZOlMye&html=&pos=3&folt=kw-top'
    final_url = get_final_url(url)
    print(final_url)