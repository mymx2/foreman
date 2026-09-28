# Naming conventions / 命名与文案规范

本文维护展示区命名、标题栏与 subtitle 规则。执行生成前按本文产出文本，交付前按本文自检。

## Outer FRAME 名称

```text
<team>_<business>·<scene>·衍生展示区
```

字段说明：

- `<team>`：团队或业务线，例如 `产品团队`、`设计系统团队`。
- `<business>`：业务模块，例如 `登录流程`、`订单管理`、`权限设置`。
- `<scene>`：showcase 聚焦场景，例如 `新版登录流`、`异常态对照`。
- 分隔符固定：团队与业务之间用半角下划线 `_`；业务、场景、`衍生展示区` 之间用全角中点 `·`。
- 末尾固定 `衍生展示区`，不要写 `Showcase`。

正确：

```text
产品团队_登录流程·新版登录流·衍生展示区
```

错误：

```text
登录流程·Showcase
新版登录流 衍生展示
产品团队-登录流程-衍生展示区
```

## Titlebar 三段标题

Titlebar 三段顺序固定为：**产品 / 主题 / 日期**。日期永远放最后。

| 段 | 内容 | 默认字号 | 默认颜色 |
|---|---|---:|---|
| 1 | `<product>` 产品/项目名，例如 `Product Mobile` | 96 | 当前 preset 主前景色 |
| 2 | `<topic>` 当前 showcase 主题，例如 `官网流程总览` | 96 | 当前 preset 主前景色 |
| 3 | `<date>` 日期，使用 `YYYY.M.D` | 96 | 当前 preset 弱化前景色 |

日期规则：

| 场景 | 格式 | 示例 |
|---|---|---|
| 单日 | `YYYY.M.D` | `2026.5.20` / `2026.12.3` |
| 区间 | `YYYY.M.D – YYYY.M.D` | `2026.5.10 – 2026.5.20` |

不要使用 `5.20` 或 `2026-05-20`。

## Subtitle TEXT 模板

```text
<客户端> · <链路/设计稿说明>
```

- `<客户端>`：根据 UI 场景写承载端，使用英文小写。常用值：`mobile` / `desktop` / `web` / `tablet` / `mobile + desktop` / `mobile + web` / `desktop + web`。
- 多端用 ` + ` 连接，推荐顺序：`mobile + tablet + desktop + web`。
- `<链路/设计稿说明>`：写一句短中文，说明这是哪个链路或哪类设计稿。
- 不要写 `3 屏对照`、`5 个状态` 这类数量信息；数量从画面本身可见，标题区应优先表达业务语义。
- 不要用 `screens` / `cards` / `flows` 作首段；首段必须回答「这是哪个端的 UI」。
- 不要用括号重复 titlebar 的 `<topic>` 或大标题。

正确：

```text
desktop · WorkBuddy 中调用网盘链路
web · 官网购买页流程
mobile + desktop · 登录链路设计稿
```

错误：

```text
desktop · 3 屏对照（WorkBuddy 中调用网盘链路）
screens · 3 屏对照
web · 官网流程总览（官网流程总览）
```

## Mini-title 命名

- 每个 cell 必须有 mini-title。
- mini-title 保持短句，优先写状态 / 页面 / 变体名。
- 出现 `新增` / `修改` / `废弃` / `灰度` 等状态词时，使用 skeleton-spec 的 Style C/D 状态色样式。
