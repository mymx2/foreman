---
name: idea-mcp
description: >
  通过 idea-mcp 的 execute_tool 调用 IntelliJ IDEA 项目模型：符号与文本定位（含 jar 内库类）、
  PSI 与 inspection 脚本、编译与代码检查、引用感知重构、运行配置与 xdebug 断点调试、
  IDE 管理的数据库连接与 SQL 查询。当目标项目已在 IDE 中打开，需要定位符号、反查库类、
  验证编译、观察 live 请求或查询数据库时使用。不适用于执行 Gradle/Maven 构建任务、
  IDE 未打开的项目，以及 rg 即可完成的纯文本查找。
when_to_use: idea-mcp, intellij, ide 索引, 符号定位, 库类反查, 断点调试, xdebug, 编译检查, 引用感知重构, 数据库查询
---

# idea-mcp

idea-mcp 是 IntelliJ IDEA 的 MCP 服务，暴露 IDE 的索引、编译器、调试器与数据库工具。IDE 索引已经知道答案时，不要从源码重新推导。

## Outcome Contract

- Outcome: 通过 idea-mcp 拿到 IDE 项目模型的实时答案（定位、编译、调试、数据库），替代终端重新推导。
- Done when: 选对工具族、参数格式正确、每次调用带 projectPath，结果来自 IDE 索引而非字面文本猜测。
- Evidence: 工具返回的结构化 JSON、编译问题清单、断点处的栈与变量值、SQL 结果集。
- Authorization: 定位、检查、调试、查询类调用直接执行；重构与文件创建等编辑操作遵循当前轮次指令。

## 调用机制

唯一入口是 `execute_tool`，两个参数：

- `command`: 工具名加参数的命令行字符串，格式 `--paramName value`；object/array 参数传 JSON，如 `--files '["A.kt","B.kt"]'`。
- `projectPath`: 目标项目的绝对路径，每次都传；路径不明时先不带它调用一次，服务端会列出当前打开的项目供选择。

两条零成本自助发现路径：

- 参数不明：不带参数调用该工具，返回 `Missing required parameters: ...` 列出必填项。
- 工具名不明：调用任意不存在的命令，返回全量可用工具清单。

## 调用流程

1. 确认 idea-mcp 可用；不可用按 Hard Rules 的降级链执行，不空等。
2. 确定 projectPath（当前工作目录即可），后续每次调用都带。
3. 按下方场景路由选工具，用 `--paramName value` 拼 command。
4. 读返回的结构化结果；出错时按错误文案修正（格式、必填项、项目歧义各有明确提示）。
5. 编辑类操作完成后，用 `get_file_problems` 或 `build_project` 验证编译，再做运行验证。

## 场景路由

按任务选工具族。表中必填参数来自对服务的实时探测；未列出的参数用上一节的自助发现补齐。

### 定位与反查

| 任务 | 工具 | 必填参数 |
| --- | --- | --- |
| 按名搜符号（含 jar 内库类） | `search_symbol` | `--q` |
| 光标处符号定义与文档 | `get_symbol_info` | `--filePath --line --column` |
| 文本或正则搜索（IDE 索引范围） | `search_text` / `search_regex` | `--q` |
| 方法调用链分析 | `analyze_calls` | `--symbolFqn --analysisKind` |
| 查看代码 PSI 结构 | `generate_psi_tree` | `--code --language` |
| 自定义结构化检查 | `run_inspection_kts` | `--inspectionKtsCode --contextPath` |

inspection KTS 配套：`validate_inspection_kts`（校验脚本）、`generate_inspection_kts_api`（API 参考）、`generate_inspection_kts_examples`（示例）。写 KTS 脚本前先取 API 与示例，不凭空写。

### 编译与检查

| 任务 | 工具 | 必填参数 |
| --- | --- | --- |
| IDE 全量编译 | `build_project` | 无 |
| 单文件编译与检查问题 | `get_file_problems` | `--filePath` |
| 批量 lint | `lint_files` | `--files`（JSON 数组） |

### 编辑与重构

| 任务 | 工具 | 必填参数 |
| --- | --- | --- |
| 应用补丁（PSI 感知） | `apply_patch` | patch 文本 |
| 重命名（引用感知） | `rename_refactoring` | `--pathInProject --symbolName --newName` |
| 格式化 | `reformat_file` | 文件 |
| 新建文件 | `create_new_file` | `--pathInProject` |
| 读文件、编辑器打开、文件搜索、目录树 | `read_file` / `open_file_in_editor` / `search_file` / `list_directory_tree` | 按探测 |

### 运行与 xdebug 调试

| 任务 | 工具 | 必填参数 |
| --- | --- | --- |
| 列出、启动运行配置 | `get_run_configurations` / `execute_run_configuration` | `--configurationName` 或 `--filePath --line` |
| 启动调试会话 | `xdebug_start_debugger_session` | 同上 |
| 设、删、列断点 | `xdebug_set_breakpoint` / `xdebug_remove_breakpoint` / `xdebug_list_breakpoints` | 位置模式 `--filePath --line`，ID 模式 `--breakpointId` |
| 控制会话（resume、step、stop 等） | `xdebug_control_session` | `--action` |
| 栈、帧变量、线程、调试器状态 | `xdebug_get_stack` / `xdebug_get_frame_values` / `xdebug_get_threads` / `xdebug_get_debugger_status` | 按探测 |
| 表达式求值 | `xdebug_evaluate_expression` | `--expression` |
| 按路径取值、改变量、跑到指定行 | `xdebug_get_value_by_path` / `xdebug_set_variable` / `xdebug_run_to_line` | 按探测 |

xdebug 是观察 live 请求的唯一途径：断点、栈帧、表达式求值、线程状态都来自真实运行中的应用。

### 数据库

| 任务 | 工具 | 必填参数 |
| --- | --- | --- |
| 列出、测试、创建、编辑连接 | `list_database_connections` / `test_database_connection` / `create_database_connection` / `edit_database_connection` | 按探测 |
| 列出 schema、对象、对象类型 | `list_database_schemas` / `list_schema_objects` / `list_schema_object_kinds` | 按探测 |
| 内省 schema 结构 | `introspect_schema` | `--connectionId --databaseName --schemaName` |
| 对象描述、表数据预览 | `get_database_object_description` / `preview_table_data` | 按探测 |
| 执行 SQL | `execute_sql_query` | `--connectionId --databaseName --schemaName --queryText` |
| 分页取结果、取消、历史 | `fetch_query_result` / `cancel_sql_query` / `list_recent_sql_queries` | `--resultSetId --offset` 或按探测 |

### 项目结构与配置

| 任务 | 工具 |
| --- | --- |
| 模块、依赖、仓库 | `get_project_modules` / `get_project_dependencies` / `get_repositories` |
| 打开的文件、git 状态 | `get_all_open_file_paths` / `git_status` |
| 终端命令 | `execute_terminal_command` |

## 研发循环规则

- 迭代期间跳过格式化（ktfmt、spotless 慢）；工作批次结束统一格式化，不每次保存都跑。
- 改动验证用 `get_file_problems` 或 `build_project`，不用 Gradle 编译验证每次编辑。
- 行为验证：经 `execute_run_configuration` 或 xdebug 重启应用，在 live 请求上确认，不靠打印桩。
- Gradle 终端命令保留给 idea-mcp 做不到的事：clean release build、锁文件解析、spotlessApply、bootRun。

## Hard Rules

- 定位符号、库类、编译问题时 idea-mcp 优先于 rg 与终端：IDE 索引覆盖 jar 内类，rg 看不到，且终端显示层可能混淆类名，字面输出不可信。
- 每次调用都传 projectPath；多项目同时打开时不传会产生歧义调用。
- 不臆造工具名与参数：先用「调用机制」里的两条自助发现路径核实。
- idea-mcp 不可用时降级：构建运行走 Gradle 终端，文本搜索走 rg/fd，编辑走直接文件读写；不阻塞任务空等。

## Gotchas

| 现象 | 处理 |
| --- | --- |
| `Invalid argument format: 'k=v'` | 改用 `--paramName value`；object/array 传 JSON |
| `Missing required parameters: ...` | 按列出的必填项补参，这是官方参数发现方式 |
| `Unable to determine the target project` | 补 projectPath；返回体会列出当前打开的项目 |
| `Tool 'x' not found` | 返回文本即全量工具清单，从里面挑正确名字 |
| 要给 jar 内库类设断点 | 先 `run_inspection_kts` 反查类的 virtualFile.url，再 `xdebug_set_breakpoint` |
| SQL 结果集太大 | `execute_sql_query` 拿 resultSetId，`fetch_query_result --offset` 分页 |
