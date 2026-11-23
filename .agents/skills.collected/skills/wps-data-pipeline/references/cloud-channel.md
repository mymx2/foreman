# 云端取数通道（kdocs / 金山文档）

标签只有四类，写成 `来源·结论`：

| 标签 | 含义 | 引用前必须确认 |
|---|---|---|
| `实测·可用` | 本机跑通过或已复现可用 | 能指向可执行复验命令，或指向本文件带复验命令的表行 |
| `实测·不可用` | 本机复现过失败 | 同上；拿不出复验方式的降级为 `推断` |
| `文档·未测` | 官方文档或上游参考实现里有，本机未跑 | 注明文档/代码位置；改关键路径前先小范围试一次 |
| `推断` | 无文档依据，靠机制推理 | 不得作为交付依据 |

「实测」不是修辞：凡出现处都要能指向一条可执行复验命令；**脚本未暴露入口的 action 例外**，须在该行注明「脚本无入口」。

测试环境：Windows 11；WPS 12.1.0.29690（云文档由 CEF 渲染，进程 `promecefpluginhost.exe`）；浏览器 Chrome 已登录企业账号；Python 3.13 + python-calamine。

## 外部来源（本地克隆已清理）

本文与 `local-com.md`、`data-pitfalls.md` 里带仓库名的引用，指的都是下列上游**仓库内的相对路径**，不是本技能目录里的文件。评审用的本地克隆已删除，复验请重新获取对应版本。

| 来源 | 版本 / 获取方式 | 引用形态 |
|---|---|---|
| `kdocs-skill` | v2.4.0，`https://github.com/suge168/kdocs-skill.git` | `kdocs-skill/references/...`、`kdocs-skill/scripts/...` |
| `kdocs-skill-365` | v2.5.7，SkillHub 发布产物（`skillId skill_2053082745828995072`），**无 git 仓库** | `kdocs-skill-365/references/...`、`kdocs-skill-365/SKILL.md` |
| `wps-skills` | `https://github.com/lc2panda/wps-skills.git` | `wps-office-mcp/scripts/wps-com.ps1` |

`kdocs-skill-365` 的行号只对该发布包成立：它不能 clone，SkillHub 更新后行号会漂移；重新取到包要核对内容再引用。两个 git 仓库的行号也只在对应 commit 上有效，重新 clone 后先确认版本。这类引用一律是 `文档·未测`——只作方向指引，不算本机验证过的结论；`实测·*` 的证据全在本技能自己的复验命令里，不依赖外部仓库。

## 官方接口的边界（本技能为何不走开放平台）

| 事实 | 标签 | 来源 |
|---|---|---|
| 官方 `download_file` 不支持在线文档类型下载，只支持上传的二进制文件（.docx / .xlsx / .pdf / .pptx）；在线文档要内容得走 `sheet.*` 这类细粒度读取 | `文档·未测` | `kdocs-skill/references/api/read.md:99`；`kdocs-skill-365/references/drive/read_and_download.md:106` |
| 官方返回的下载 `url` 需登录态（wps.cn / kdocs.cn 域名下要带凭据），与本技能用的内部预签名地址不是一回事 | `文档·未测` | `kdocs-skill/references/kwiki_references.md:142` |
| 限频 `429001` / 熔断 `429002` 的响应带恢复时间，期间应零请求 | `文档·未测` | `kdocs-skill-365/SKILL.md:280-281` |

官方路径对在线表格的边界很清楚：要么给不出二进制，要么给的 url 在页面外拿不动，要么被限频按住。这是本技能改走页面上下文取整本 xlsx 的原因，不是绕路取巧。

## 活着的端点

所有请求都在**目标表格所在页面的上下文**里发出（同源 + 已登录 Cookie）。不要用 curl 直接打这些接口——没有会话只会拿到登录页。

| 端点 | 方法 | 标签 | 实测结果 |
|---|---|---|---|
| `/api/v3/office/file/{file_id 或 code}/download` | GET | `实测·可用` | 200，JSON 含 `download_url`（预签名）与 `fize`（字节数） |
| `download_url`（对象存储预签名地址） | GET | `实测·可用` | 200，二进制 xlsx：文件头 `50 4b 03 04`，字节数等于 `fize`；规模数据见使用方的 inventory |
| `/api/v3/office/file/{code}/open/et` | GET | `实测·可用` | 200，返回打开表格所需信息 |
| `/api/v3/office/file/{code}/session/et` | GET | `实测·可用` | 200，返回会话信息 |
| `/api/v3/office/file/{fid}/privilege_list` | GET | `实测·可用` | 200，当前账号对该文件的权限清单 |
| `/api/v3/office/file/{code}/export` | GET | `实测·不可用` | 404，该端点不存在，导出只能走 `download` |

复验上表任意一行：在目标文件页面控制台跑 `fetch('/api/v3/office/file/<FILE_ID>/privilege_list',{credentials:'include'}).then(r=>r.status)`，拿到 200 就说明「同源 + 已登录」这个前提成立，其余端点换个路径同理。curl 复验不算——本文件的前提是页面上下文。

`download_url` 有两种，别混：

- **内部 web 接口返回的预签名地址**（上表第 2 行）：不需要 Cookie，签名自带授权，可以用 curl 在页面外下载。它带时效，取到就立刻拉。
- **官方开放平台返回的地址**：需登录态，不能 curl（`文档·未测`，来源 `kdocs-skill/references/kwiki_references.md:142`）。本技能不走这条。

## code 与 file_id 的关系

| 事实 | 标签 |
|---|---|
| 分享链接里的短码（形如 `crmZOQohQZl2`）与数字 ID（形如 `123273837797`）是两个不同的值 | `实测·可用` |
| `download` / `open` / `session` / `privilege_list` 对两者都接受，返回同一份文件 | `实测·可用` |
| 数字 ID 稳定，短码跟随分享链接，可能随重新分享而变 | `实测·可用` |
| 归档与对账应以数字 file_id 为主键，短码只用于人找文件 | `推断`（工程惯例，非实测） |
| `download_url` 有效期未测；取到后立刻拉，过期重取 | `推断` |
| 其它 `/api/v3/office/file/{id}/*` 子路径可能还有可用端点 | `推断`（不要靠猜接口工作） |

## 读取的天花板

两层机制各自独立，都会让「读到的行数」小于「表里的行数」。

**第一层：页内虚拟化。** 页面上下文里调 `getRangeContents()` 读区域，请求 500 行，只返回 62 行。渲染层只持有可视窗口附近的数据。

**第二层：服务端首屏截断。** 官方 `read_file` 对表格类不传 `sheet_range` 时只读默认首屏区域，单次返回数据有限；返回体里的 `warnings` 字段必须检查，它会说明实际读了哪个范围、建议怎么改（`文档·未测`，来源 `kdocs-skill-365/references/drive/read_and_download.md:237`、`:239`、`:286`）。

- 合法用途：抽查几行核对、确认表头文字与列顺序。
- 非法用途：当全量数据源、算总数、验证下载文件完整性（`--list` 的行数才是完整性依据）。
- 状态：第一层 `实测·不可用`（请求 500 行，只返回 62 行——截断是实测到的失败，不是可用）；第二层 `文档·未测`——本技能不调 `read_file`，列在这里是给「为什么不用官方读接口」留对照。

## 失败时的判断顺序

1. `fetch` 返回 HTML 或 401 → 先确认上下文是不是目标文件页、是否已登录，而不是怀疑接口。
2. 返回 200 但没有 `download_url` → 读返回体错误字段，通常是权限或文件类型问题。
3. `download_url` 拉下来不是 `PK\x03\x04` → 多半过期被重定向到登录页，重取一次。
4. 受保护文档（`SecureDocumentError` / `forbidProtectedFile`）→ 所有导出接口一律失败。这和「未登录」是两种不同的失败：未登录换有权限的会话还能救，受保护文档换谁都没用，只能提示用户去源端处理，别在接口上重试。`文档·未测`，来源 `kdocs-skill/references/kwiki_references.md:142`。
5. 以上都不成立 → 走回退路径（人工下载 + 同一解析脚本），不要在接口上继续猜。

## 已封死的通道（可复验清单）

试过、不通。这些会随产品版本变化，所以每条都带核实日期与 30 秒复验命令。**怀疑已解封时先跑复验，现象没变就不要再试。**

| # | 通道（收窄到具体地址/对象） | 结论 | 核实日期 | 30 秒复验 | review_by |
|---|---|---|---|---|---|
| 1 | 企业开放接口 / 自建应用授权 | 走完授权调用报 `enterprise_denied`；套餐为商业协作版，不含企业文档二次开发接口 | 2026-11-23 | 前提：页面内 `fetch('/api/v3/office/file/<FILE_ID>/privilege_list',{credentials:'include'}).then(r=>r.status)`，200 说明同源登录态成立；结论：用同一自建应用凭据调任一业务接口，仍返回 `enterprise_denied` 即不变 | 2027-02-28 |
| 2 | SkillHub MCP 工具目录（`mcp-center.wps.cn`） | 该 MCP 目录地址 403。只说这个目录进不去，不等于 SkillHub 不可用 | 2026-11-23 | 已登录访问该地址任意工具列表页，看是否仍 403。**即便 403 消失也只代表目录可达，不代表能取到完整 xlsx** | 2027-02-28 |
| 3 | 本机 WPS 加载项 / COM / JSAPI | 云文档由 CEF 渲染，加载项不加载；同机 `et.exe` 的 `Workbooks.Count` 为 0 | 2026-11-23 | 打开云文档后执行 `Dispatch("Ket.Application").Workbooks.Count`，为 0 即仍不适用 | 2027-02-28 |
| 4 | `/export` 端点 | 返回 404 | 2026-11-23 | 页面内 `fetch('/api/v3/office/file/<CODE>/export',{credentials:'include'}).then(r=>r.status)`，仍 404 即不变 | 2027-02-28 |

第 2 行只管 MCP 目录那一个地址。SkillHub 的分发通道（二进制与 skill 包分发）走 `wpsai.wpscdn.cn/skillhub/pro`，本次没单独测，不在第 2 行的结论范围内——`文档·未测`，来源是 `kdocs-skill/scripts/setup.cjs:22` 的默认 CDN 配置。

判定原则：

- 复验只做**一次**，结果记回本表，不要同一天反复试。
- 报错换形态不等于能力可用，以「能否拿到完整 xlsx」为唯一通过标准。
- 同一产品不同版本的口径可能相反（例：`.ksheet` 的创建方式在 v2.4.0 与 v2.5.7 的文档里描述相反）；复验以 CLI `--help` 的实际支持为准，不以文档为准。
- `review_by` 过期不代表结论作废，代表**需复验后才能引用**。
