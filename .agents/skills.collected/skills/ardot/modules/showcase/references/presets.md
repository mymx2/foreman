# Presets / 主题配置说明

本技能内置四个 preset。实际数值配置在 `../assets/preset-config.json`（模块根目录的 `assets/`），本文说明选择方式、覆盖方式和字段语义。

## 选择 preset

| 使用场景 | Preset |
|---|---|
| 内部评审、异步截图、设计师交付 PM/研发 | `dark-review`（默认） |
| 浅色产品环境、打印、正式文档 | `light-review` |
| 护眼浏览、不抢画板内容的中性底 | `gray-review` |
| 大屏演示、周会汇报、远距离观看 | `presentation` |

没有明确场景时默认 `dark-review`。黑色背景能把画板从 Ardot 画布环境里隔离出来，截图更像一张完整交付物。

## 自然语言主题切换（$themeAliases）

`preset-config.json` 顶层有 `$themeAliases`，把日常说法映射到 preset 名，用户不需要记 preset 名：

| 用户说法 | 解析到 |
|---|---|
| 白底 / 浅色 / 亮色 / 打印版 | `light-review` |
| 灰底 / 浅灰 / 中性灰 / 护眼 | `gray-review` |
| 黑底 / 深色 / 暗色 / 默认 | `dark-review` |
| 演示 / 大屏 / 投屏 / 纯黑 | `presentation` |

解析逻辑：将用户主题词在各 preset 的别名词表里做包含匹配，命中即用对应 preset；匹配不到回退 `dark-review` 并提示一次。新增 preset 时同步在 `$themeAliases` 补一行别名词表。

## 对比度配对（切主题必守）

**每个 preset 的 `background` 与主前景色（title / groupLabel / miniTitle）是成对定义的，切换主题时必须一起换。** 不允许只改背景留旧文字色 —— 会出现白底白字、灰底浅字等读不清的结果。

| 背景明暗 | 主前景 | 弱化信息 | divider |
|---|---|---|---|
| 深（dark-review / presentation） | white-100 | white 40% | white 16% |
| 浅白（light-review） | black-90 | black 40% | black 16% |
| 浅灰（gray-review） | gray-900 近黑 | near-black 50% | near-black 12% |

状态色后缀（info/warning/error）所有主题共用同一组 `$stateTokens`，因为蓝/橙/红在深浅底上都有足够对比度。

## 覆盖机制

允许用户对本次任务临时覆盖任意字段，例如：

```text
用 dark-review，但标题字号改成 120，背景改成纯黑。
```

实现方式：读取 preset 后，将用户覆盖字段 deep-merge 到配置上。覆盖只对当前任务生效，不写回 `preset-config.json`。

如果用户需要长期变体，应新增 preset，而不是每次临时覆盖。

## 字段结构

每个 preset 保持同一结构：

```json
{
  "name": "dark-review",
  "background": {
    "color": { "r": 0, "g": 0, "b": 0, "a": 0.9 },
    "tokenName": null
  },
  "title": {
    "fontFamily": "PingFang SC",
    "fontWeight": "Regular",
    "fontSize": 96,
    "color": { "r": 1, "g": 1, "b": 1, "a": 1 },
    "tokenName": "white-100"
  },
  "subtitle": {
    "fontFamily": "PingFang SC",
    "fontWeight": "Regular",
    "fontSize": 36,
    "color": { "r": 1, "g": 1, "b": 1, "a": 0.4 },
    "tokenName": null
  },
  "outer": {
    "cornerRadius": 100,
    "cornerSmoothing": 0,
    "clipContent": false
  },
  "groupLabel": {},
  "miniTitle": {},
  "miniTitleSuffix": {},
  "miniTitleSuffixState": {},
  "columnDivider": {},
  "spacing": {}
}
```

`tokenName: null` 表示该字段有意使用 raw color，通常是透明度驱动的弱信息色。其他字段在目标文件存在对应 token 时应绑定 token。

## v1.0.7+ 新增字段

```json
"outer": {
  "cornerRadius": 100,
  "cornerSmoothing": 0,
  "clipContent": false
},
"miniTitleSuffixState": {
  "info":    { "$ref": "state-info" },
  "warning": { "$ref": "state-warning" },
  "error":   { "$ref": "state-error" }
},
"columnDivider": {
  "type": "RECTANGLE",
  "width": 1,
  "height": "fill_container",
  "fill": { "$ref": "divider-subtle" }
}
```

说明：

- `outer.cornerRadius` 控制展示区外框圆角，默认 100px；不要生成方角 outer。
- `miniTitleSuffixState` 用于 Style C/D 的状态色后缀。
- `columnDivider` 只用于不同能力/模块边界，不用于同一链路多状态。用 `RECTANGLE + height:"fill_container"` 自动撑满行高，禁止用 `LINE + rotation + 写死 length`（会导致分割线只显示上半段）。
- `$ref` 指向 `preset-config.json` 顶层 `$stateTokens`。
- 本配置默认不绑定具体项目变量 ID；团队可在本地 fork 中自行补充 `ardotVariableId`。

## Preset 差异

| Field | `dark-review` | `light-review` | `gray-review` | `presentation` |
|---|---|---|---|---|
| `background.color` | black 90% | white 100% | gray `#F1F2F4` | black 100% |
| `title.fontSize` | 96 | 96 | 96 | 120 |
| `title.fontWeight` | Regular | Regular | Regular | Medium |
| `title.color` | white | black 90% | gray-900 近黑 | white |
| `subtitle.color` | white 40% | black 40% | near-black 50% | white 40% |
| `groupLabel.fontSize` | 60 | 60 | 60 | 72 |
| `groupLabel.color` | white | black 90% | gray-900 近黑 | white |
| `miniTitle.color` | white | black 90% | gray-900 近黑 | white |
| `outer.cornerRadius` | 100 | 100 | 100 | 100 |
| `spacing.*` | 默认间距 | 默认间距 | 默认间距 | 放大间距 |

## 新增 preset

新增第五个 preset 时：

1. 在 `preset-config.json` 顶层添加同结构对象（务必成对定义 background + 主前景色，保证对比度）。
2. 在 `$themeAliases` 补一行该 preset 的自然语言别名词表。
3. 更新 SKILL.md 的 preset 表和「自然语言切换主题」表。
4. 更新本文的选择表、对比度配对表和差异表。

不要用 preset 改结构，例如「无 titlebar preset」「一列两屏 preset」。结构变化应属于新技能或新 workflow，不应藏在 preset 中。

## 覆盖示例

### 加重标题

```json
{
  "preset": "dark-review",
  "overrides": {
    "title": { "fontSize": 120, "fontWeight": "Medium" }
  }
}
```

### 录屏时使用纯黑背景

```json
{
  "preset": "dark-review",
  "overrides": {
    "background": { "color": { "r": 0, "g": 0, "b": 0, "a": 1 } }
  }
}
```

### light-review 使用 presentation 标题字号

```json
{
  "preset": "light-review",
  "overrides": {
    "title": { "fontSize": 120 }
  }
}
```
