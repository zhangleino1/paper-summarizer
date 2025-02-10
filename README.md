# 智能学术论文助手：一站式高效论文阅读与总结 AI-Agent

详细的教程： 
- [我开源了：学术论文总结AI-Agent！](https://mp.weixin.qq.com/s/ij_nsm56bdjUV3KkEtoY4g?token=1854334933&lang=zh_CN)

- [Firecrawl本地docker安装,方便国内用户的，因为下载镜像太难了](https://mp.weixin.qq.com/s/Zzs4XtCj_xsnlmM0PtOxNg?token=1854334933&lang=zh_CN)
- [运行效果视频，方便理解](https://www.bilibili.com/video/BV1CiUSYGEYP/)
- [google colab 运行，不用本地安装](https://colab.research.google.com/drive/1GoJxK4ynMnRxSrL1p5hPZH4gqhftmyI2?usp=drive_link)
  
这张图展示了一个自动化处理学术论文的工作流程
![ai agent工作流程](/workfloow.png "Magic Gardens")


具体介绍如下：
```
# 安装依赖
pip install requests beautifulsoup4 python-dotenv backoff crewai

agent_crewai.py 程序入口
# 注意设置 QQ_EMAIL 和 QQ_PASSWORD 的环节变量，我这里是把谷歌学术订阅转发到qq邮箱了
```
### 1. **论文阅读痛点**：
   在阅读学术论文时，用户遇到了以下几个常见问题：
   - 网络不稳定，导致无法方便地查看论文内容。
   - 需要逐个点击链接，查看每篇论文，操作繁琐。
   - 尽管可以看懂英文论文，但由于语言障碍，阅读速度较慢，效率较低。
   - 快速梳理论文的创新点和核心内容耗费大量时间和精力。

### 2. **前端邮箱获取学术论文推送**：
   这个模块展示了如何通过邮箱接收来自 Google 学术订阅、Gmail 或 QQ 邮箱中的学术论文推送。通过以下几个步骤获取最新的论文信息：
   
   - **imap协议读取邮件**：系统首先使用 imap 协议访问邮箱中的未读学术订阅邮件。
   - **通过内容解析技术抓取链接**：系统会自动抓取邮件中包含的学术论文链接。
   - **从邮件中提取论文链接**：从推送邮件中提取出论文的链接，供后续流程使用。

### 3. **Firecrawl平台处理论文链接**：
   - **接收论文链接到 Firecrawl 平台**：Firecrawl 平台是一个爬虫服务，它可以根据输入的 URL 抓取整个网站的内容，并将其转换为干净的 Markdown 或结构化数据。
   - **抓取论文内容**：系统会抓取论文的标题、摘要以及其他有价值的信息，为后续处理提供基础数据。
### 4. **Multi-Agent Crews 论文智能处理框架**：
   该部分展示了多智能体系统如何协同工作来处理论文数据：
   
   - **网页抓取Agent**：这个智能体负责抓取论文的网页内容，并将其提取为干净的文本数据。
   - **论文翻译Agent**：在获取原始论文内容后，翻译Agent会使用大语言模型（如 LLaMA、MiniGPT 等）对文本进行翻译，帮助用户克服语言障碍。
   - **论文提取Agent**：这个Agent负责提取论文的核心内容，包括研究方法、解决方案和创新点，为用户生成精简且有用的论文摘要。
   - **论文整理Agent**：根据论文的类型和用户需求，生成不同格式的 Markdown 文件，便于用户整理和阅读。

### 5. **最终输出**：
   - 根据不同类别的论文，系统会输出结构化的 Markdown 文件。这些文件内容清晰，便于用户理解和直接使用，如整理笔记、写作报告等。

### 总体技术框架：
- **Firecrawl**：这是一个用于网页抓取和数据处理的框架，负责抓取论文内容，并将其转化为 LLM（大语言模型）可读的数据格式。  url:https://github.com/mendableai/firecrawl
  如果你觉得调用firecrawl收费，我这里有打好的镜像，可以直接下载安装 链接：https://pan.quark.cn/s/1fb1db26633d
- **CrewAI**：这是一个多智能体协作框架，智能体能够扮演不同角色协同工作，共同完成复杂任务，如抓取、翻译和提取论文内容等。url:https://www.crewai.com/
- **ollama**：  方便集成各种大模型 https://ollama.com/

这个工作流程实现了从接收论文推送邮件到输出最终可阅读和使用的论文摘要的自动化处理，大大提高了学术论文的阅读和总结效率，特别适合研究人员和学术从业者使用。
## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=zhangleino1/paper-summarizer&type=Date)](https://star-history.com/#zhangleino1/paper-summarizer&Date)
