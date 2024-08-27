# 谷歌学术推送论文整理 ai agent

要生成和设置代码中的 JSON 配置文件和环境变量，请按照以下步骤操作：

### 1. 生成 `credentials.json`
`credentials.json` 文件是用于Google API的OAuth 2.0客户端ID文件，你可以通过以下步骤生成：

1. **创建一个Google Cloud项目**:
   - 访问 [Google Cloud Console](https://console.cloud.google.com/).
   - 创建一个新的项目。

2. **启用Gmail API**:
   - 在项目仪表盘中，选择 "API & Services" > "Library"。
   - 搜索 "Gmail API"，然后点击 "Enable" 按钮启用。

3. **创建OAuth 2.0凭证**:
   - 选择 "API & Services" > "Credentials"。
   - 点击 "Create Credentials" 按钮，选择 "OAuth 2.0 Client IDs"。
   - 在 "Application type" 选择 "Desktop app"，然后输入名称。
   - 点击 "Create" 后，你可以下载 `credentials.json` 文件。

4. **将 `credentials.json` 文件放到你的项目目录**。

### 2. 设置环境变量 `.env`

`dotenv` 库用来加载环境变量。在代码中，你需要设置 `SERPAPI_API_KEY` 以及任何其他敏感信息。

1. **创建 `.env` 文件**:
   在你的项目根目录下创建一个名为 `.env` 的文件。

2. **配置 `.env` 文件**:
   编辑 `.env` 文件，添加以下内容：

   ```env
   SERPAPI_API_KEY=你的SerpAPI密钥
   ```

   你可以在 [SerpAPI官网](https://serpapi.com/) 注册并获取API密钥。

### 3. 启动项目

1. **安装依赖**:
   确保你已经安装了项目中所需的Python库。你可以使用 `pip` 来安装:

   ```bash
   pip install -r requirements.txt
   ```

2. **运行项目**:
   在终端中运行你的主程序：

   ```bash
   python agent.py
   ```

这将启动程序，读取你的 Gmail 中未读的谷歌学术邮件，处理论文标题和摘要，并将处理结果保存为 `Markdown` 文件。

如果有任何问题，可以逐步检查日志输出，查看是否有任何配置问题。