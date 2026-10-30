# 应用特例参考

主文档只写通用方法。特定产品的版本缺陷、错误码、COM 差异放在这里，按需查阅，不要把某一台机器或某一版本的事实写进主流程。

## IM / Webhook

- 部分 IM 的 webhook 在关键词缺失或加签校验失败时返回非 0 `errcode`（例如某平台返回 `310000`）。排错顺序：先查关键词是否命中、再查加签时间戳偏差、最后查机器人是否被移出群。
- 发图通常需要图文/markdown 类型消息，直接发纯文本消息体会被忽略或报错。

## Excel 类应用

- `xlwings` 不支持 WPS。没装 Office 但装了 WPS（Windows）时，用 `win32com.client.Dispatch` 直接驱动：先试 `KET.Application`，失败回退 `ET.Application`，再失败查注册表。
- 已知部分 WPS 版本 COM 接口整体失效，遇到时回退到旧版本或改用 openpyxl 直接读写文件（放弃宏、透视表、公式重算）。
- WPS 个人版无 VBA 支持，需要宏/透视表的流程无法在 WPS 上完成。
- 写完必须 `close + save`（WPS COM 路径为 `Close(SaveChanges:=True)`），否则文件被进程锁住。
- 写完后列宽全是 `#####` 表示需要 `auto-fit-columns`；格式码用 US notation（`,` 分组、`.` 小数），Excel 会按本地化显示。

## 桌面应用自动化

- **CEF / Electron 内嵌页面**：若 UIA 只能看到 `Chrome Legacy Window` 且其下无行级节点，通常是渲染进程无障碍树未开启，而不是宿主不支持语义。此时标记 `embedded-web-no-bridge`，在交付说明里要求页面级桥接或人工接管，不要把坐标脚本标成已验收。
- **Qt / 自绘应用**：先检查完整后代节点，确认目标确实未暴露 `name/auto_id/role/value/action` 后才降级到 OCR。抽屉、滑出面板常是独立顶层窗口（`GW_OWNER` 指向主窗口），不在主窗口截图里。
- **多显示器**：窗口可能位于负坐标（副屏在主屏上方或左侧）。`GetWindowRect` 返回 `-32000` 附近说明窗口最小化，不是真实位置。

## 数据库 / 输出

- 写库前确认驱动版本与目标库匹配；批量写入用事务，失败回滚，不要逐行自动提交。
