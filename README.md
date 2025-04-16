# QuakeICP-Finder
通过网络空间资产测绘平台（quake）来检索域名备案的问题。旨在使用尽可能少的积分，发现更全的备案信息。该项目拥有缓存功能。能保存每一次查询的结果，避免重复查询浪费积分。月末积分没用完的朋友可以用该工具消耗掉积分。


#### 示例:  
```bash
python3 QuakeICP-Finder.py 北京奇虎科技有限公司
```
![image](https://github.com/user-attachments/assets/12b52030-e590-495a-a448-7ca1dc72c071)
![image](https://github.com/user-attachments/assets/b63399ac-81c0-4c2e-af6c-d696bd4c0f8b)
消耗积分大致计算方法
每迭代以此大约消耗20积分，对于资产少的公司大约只需迭代2-5次

```bash
python3 QuakeICP-Finder.py -s //打印所有缓存的内容
```

![image](https://github.com/user-attachments/assets/18423282-f549-4730-a6b3-dfad06d1b911)
![image](https://github.com/user-attachments/assets/93abe7f3-890a-4c84-bfb2-5d1d002e0c6f)
```bash
python3 QuakeICP-Finder.py --search 奇虎
python3 QuakeICP-Finder.py --search qihoo.cn //模糊搜索
```
![image](https://github.com/user-attachments/assets/aeebd7bf-4ef2-4f45-b3a6-ea80b28bc399)
![image](https://github.com/user-attachments/assets/e1ab68b2-2f56-4be8-b7f9-58056e250b68)


#### 输出文件内容:
执行脚本后会在当前目录下生成quake_icp_cache_list.json文件用作保存历史的备案查询信息。
![image](https://github.com/user-attachments/assets/04cd7264-c771-4871-befb-15c82d65fa20)


### 使用方法

**一、 环境准备**

1.  **Python 环境:** 确保你的系统中安装了 Python 3 (推荐 Python 3.6 或更高版本)。
2.  **安装依赖库:** 脚本需要 `requests` 库来发送 API 请求。打开你的终端或命令行，运行以下命令安装：
    ```bash
    pip install requests
    ```
3.  **获取 Quake API Key:**
    *   登录 Quake 系统 ([https://quake.360.net/](https://quake.360.net/))。
    *   进入“个人中心”。
    *   找到并复制你的 API Key。

**二、 配置 API Key (重要！)**

为了安全起见，**强烈建议**使用环境变量来设置 API Key，而不是直接写在代码里。

*   **Linux / macOS:**
    ```bash
    export QUAKE_API_KEY='你的实际API Key粘贴在这里'
    ```
    (注意：`export` 只在当前终端会话有效。要永久生效，请将其添加到你的 shell 配置文件中，如 `.bashrc`, `.zshrc` 或 `.profile`)
*   **Windows (CMD):**
    ```bash
    set QUAKE_API_KEY=你的实际API Key粘贴在这里
    ```
    (只在当前 CMD 窗口有效)
*   **Windows (PowerShell):**
    ```bash
    $env:QUAKE_API_KEY='你的实际API Key粘贴在这里'
    ```
    (只在当前 PowerShell 会话有效)

**备选方案 (不推荐):** 如果你确实无法设置环境变量，可以在脚本运行时通过 `-k` 参数提供 Key，但这会在命令行历史中留下记录，不够安全。

**三、 运行脚本**

将代码保存为一个 Python 文件（例如 `QuakeICP-Finder.py`）。然后可以通过命令行运行。

1.  **查询单个公司:**
    ```bash
    python QuakeICP-Finder.py "公司的完整备案主体名称"
    ```
    *   示例: `python QuakeICP-Finder.py "北京奇虎科技有限公司"`
    *   这会使用环境变量 `QUAKE_API_KEY`。

2.  **查询单个公司 (使用 `-k` 指定 Key):**
    ```bash
    python QuakeICP-Finder.py -k "你的API Key" "公司的完整备案主体名称"
    ```

3.  **从文件批量查询:**
    *   创建一个文本文件 (例如 `company.txt`)，每行包含一个完整的公司备案主体名称，使用 UTF-8 编码保存。
        ```
        北京奇虎科技有限公司
        腾讯云计算（北京）有限责任公司
        北京百度网讯科技有限公司
        ```
    *   运行命令:
        ```bash
        python QuakeICP-Finder.py -f company.txt
        ```
    *   如果需要同时指定 Key:
        ```bash
        python QuakeICP-Finder.py -k "你的API Key" -f companies.txt
        ```

4.  **搜索本地缓存:**
    *   搜索公司名称中包含 "奇虎" 的记录：
        ```bash
        python quake_icp_query.py --search 奇虎
        ```
    *   搜索域名中包含 "tencent.com" 的记录：
        ```bash
        python quake_icp_query.py --search qihoo.cn
        ```
    *   **注意:** 搜索功能**不**会调用 API，只查询本地 `quake_icp_cache_list.json` 文件。

5.  **汇总显示缓存内容:**
    ```bash
    python quake_icp_query.py -s
    ```
    *   这会加载缓存文件，并按公司名称、再按备案号排序后，打印所有缓存的记录。同样**不**会调用 API。

**四、 命令行参数详解**

```
usage: QuakeICP-Finder.py [-h] [-k APIKEY] [-f FILE] [-s] [--search TERM] [--cache-file CACHE_FILE]
                          [--batch-size BATCH_SIZE] [--max-iterations MAX_ITERATIONS] [--delay DELAY]
                          [--retry-delay RETRY_DELAY]
                          [company_name]

查询公司备案信息，支持缓存和迭代排除，并可汇总缓存内容。

options:
  -h, --help            show this help message and exit

查询选项 (默认行为):
  -k, --apikey APIKEY   Quake API Key (优先使用 QUAKE_API_KEY 环境变量) (default: None)
  -f, --file FILE       包含公司名称列表的文件 (每行一个) (default: None)
  company_name          要查询的单个公司名称 (如果未使用 -f) (default: None)

缓存汇总选项:
  -s, --summarize       解析并汇总打印当前的缓存文件内容，不执行 API 查询。 (default: False)
  --search TERM         在缓存中搜索公司名称或域名，不执行API查询 (default: None)

配置选项:
  --cache-file CACHE_FILE
                        指定缓存文件路径 (default: quake_icp_cache_list.json)
  --batch-size BATCH_SIZE
                        每次迭代查询的记录数 (default: 20)
  --max-iterations MAX_ITERATIONS
                        最大迭代次数 (default: 100)
  --delay DELAY         每次迭代请求间的延时(秒) (default: 0.2)
  --retry-delay RETRY_DELAY
                        遇到速率限制时的重试延时(秒) (default: 2.0)
```

*   **输入选项 (必须选一):**
    *   `-f FILE` 或 `--file FILE`: 从指定文件读取公司列表。
    *   `company_name`: 直接在命令行提供单个公司名称。
    *   `--search`: 搜索缓存中的 `公司名`或`域名`。
    *   `-s`: 汇总显示缓存。
*   **`-k APIKEY` 或 `--apikey APIKEY`:** 手动指定 API Key，会覆盖环境变量。
*   **`--cache-file FILE`:** 如果你想把缓存文件存放在其他位置或使用不同名称，用这个参数指定。
*   **`--batch-size SIZE`:** 控制每次迭代向 API 请求多少条数据。较小的值可以减少单次请求可能遇到的问题，但会增加迭代次数。
*   **`--max-iterations NUM`:** 防止脚本无限运行的安全措施。如果达到这个次数还没查完，会停止并给出警告。
*   **`--delay SEC`:** 控制每次 API 请求之间的基本等待时间（秒），用于避免触发 API 的速率限制。如果遇到 `q3005` 错误，应**增加**此值。
*   **`--retry-delay SEC`:** 当脚本检测到 API 返回速率限制错误时，会等待这么长时间再重试当前失败的请求。

**五、 输出说明**

*   **`[缓存]`:** 与加载、保存或命中缓存相关的日志信息。
*   **`[*]`:** 正常的执行流程信息，如开始查询、API 调用成功、处理批次等。
*   **`[警告]`:** 可能出现的问题或需要注意的情况，如排除列表过长、缓存加载失败、达到最大迭代次数等。
*   **`[错误]`:** 查询过程中发生的错误，如 API 返回错误码、网络请求失败、解析失败等。通常会导致当前公司的查询终止。
*   **最终结果:** 对于查询成功的公司，会列出找到的唯一 ICP 记录，按备案号升序排列，显示域名和备案号。对于查询失败的公司，会提示失败。
*   **汇总统计:** 最后会打印本次运行查询的公司总数、成功数和失败数。

**六、 缓存文件 (`quake_icp_cache_list.json`)**

*   脚本会在其运行的目录下自动创建或更新这个文件。
*   文件格式为 JSON，顶层是字典，键是查询过的**公司名称**，值是一个**列表**，列表中的每个元素是一个代表 ICP 备案信息的**完整对象**（字典）。
*   **缓存更新逻辑:** 只有当某次查询运行时，发现了**新的**、且主体单位**精确匹配**的备案记录（通过 `licence` 字段判断是否新），该公司的缓存才会被更新。如果某次运行没有发现任何新的备案记录，即使 API 返回了数据，缓存文件也不会被修改。
*   **手动清理:** 如果你想对某个公司进行完全重新查询，可以手动编辑 JSON 文件删除对应的公司条目，或者直接删除整个 `quake_icp_cache_list.json` 文件。


### 注意事项
如遇到资产、备案域名非常多的公司例如百度，会消耗大量积分。每一次迭代默认为20条数据即20积分，运行时可随时使用ctrl+c终端程序。

### TODO（可选）
接下来的开发/维护计划。

## License
遵守的协议
