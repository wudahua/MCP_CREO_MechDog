# 换电脑、换 Agent

MCP_CREO_MechDog 0.2.4 在安装 Creo 的 Windows 电脑上运行，通过本地 stdio MCP 调用。种子是可复制的原生 PRT 文件，不依赖某个 Agent 的聊天记录。本版没有远程 HTTP 服务入口。

## 同一电脑换 Agent

在另一个支持启动本地 stdio MCP 的客户端中，配置同一个安装目录下的 Python 和 `server.py`。采用客户端需要的格式，以安装生成的 `client-config.json` 为准，例如：

```json
{
  "mcpServers": {
    "MCP_CREO_MechDog": {
      "command": "C:\\MCP_CREO_MechDog\\.venv\\Scripts\\python.exe",
      "args": ["C:\\MCP_CREO_MechDog\\server.py"]
    }
  }
}
```

多个客户端可共用同一安装目录和种子库。同目录的 `models/`、`jobs/` 保存受管模型及任务；继续修改时调用 `creo_list_models` / `creo_inspect_model` 查询最新模型 ID 和 revision，再顺序提交。不要沿用旧聊天里可能过期的 revision。打开一个 Creo 会话，确认 `creo_session_status.connected == true`。

## 换到另一台电脑

1. 在目标 Windows x64 电脑准备 Creo 10、匹配 Toolkit SDK、MSVC x64 / Windows SDK、Python 3.12+ x64 和可用的 Toolkit 运行许可。本机实测使用 Creo 10.0.0.0。
2. 下载包含 2026-10-11 建模增量的 0.2.4 源码包，内附 `seed_library/`。源码解压到例如 `C:\MCP_CREO_MechDog`，执行：

   ```powershell
   .\setup.ps1 -CreoRoot 'C:\Program Files\PTC\Creo 10.0.0.0'
   ```

   填写目标机真实的 Creo 路径；其他程序路径选项见 [INSTALL.md](INSTALL.md)。重新生成本机环境、执行器和客户端配置，不直接复制原电脑的 `.venv`、二进制、`config.json` 或会话 ID。
3. 安装器自动验证并注册随源码的种子库。调用 `creo_list_seeds` 确认可用数量为 3。若另有原始库目录，可用 `creo_install_seed_library(directory=...)` 注册；无需向 Agent 提供种子内部 ID。步骤见 [SEED_LIBRARY.md](SEED_LIBRARY.md)。
4. 将新生成的 `client-config.json` 配置到目标 Agent，打开一个 Creo 会话。
5. 调用 `creo_capabilities` 确认 `version == "0.2.4"`，检查 `creo_check_environment` 和 `creo_session_status`。再创建一个小零件，核对任务成功、原生特征树和保存重载，验证目标机实际运行条件。

新 Agent 可以使用如下提示词，方括号内容必须替换为本机实际位置：

> 使用 MCP_CREO_MechDog 0.2.4 的 2026-10-11 建模增量。先检查能力、环境及 Creo 会话，调用 creo_list_seeds 确认自动种子库。需要五截面平滑翼型时使用 creo_new_airfoil_blade，截面数量和模式由本机库自动匹配。只提交一次，查询到完成，再修改一个截面的弦长及扭转，核对原生混合保留和保存重载。

Agent 通过上述 MCP 工具即可查询和使用随包种子，无需读取本机文件或执行解析脚本。自动搜索配置目录、随包目录和已注册目录，不扫描整个硬盘。

## 云端 Agent 与既有模型

纯云端 Agent 需要能在目标 Windows 电脑执行工具的本地执行端；仅填写 GitHub 仓库 URL 无法连接本地 Creo。远程 HTTP 网关尚未封装。

本版受管模型记录含本机绝对路径。将原生 PRT 复制到新电脑可以用 Creo 打开，但不能直接沿用旧电脑的 `model_id` 当作已注册模型。完整的模型记录导入、路径重定位和外部 PRT 纳管尚未封装；上述流程用于在新电脑创建新模型。同机同安装目录的 Agent 可继续使用已保存的受管模型。
