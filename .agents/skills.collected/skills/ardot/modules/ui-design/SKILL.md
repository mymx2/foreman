---
name: ui-design
description: |
  当用户在 Ardot 里要设计 UI 界面（网页、Web App、后台、落地页、移动端 App、表格、表单、组件库、设计系统）时使用，加载对应的领域设计规范。
  不适用于幻灯片与海报（另属排版类）、纯设计稿转代码（走 design-to-code 模块）。
  Triggers: "设计页面", "创建界面", "生成网站", "设计后台", "做落地页",
  "设计 App", "移动端", "小程序界面", "设计系统", "组件库规范", "design system", "design token".
metadata:
  source: 本仓
---

# UI 界面设计规范

在 Ardot 画布上做 UI 类交付物时，按交付类型加载对应的领域规范。

## Outcome Contract

- **Outcome**：产出结构清晰、符合领域惯例的界面设计稿。
- **Done when**：每个界面有明确的主目的与主操作；视觉层级成立；规范里要求的元素齐全。
- **Evidence**：界面能指出唯一主操作；主导区域明确；文字层级与间距符合所加载规范。
- **Authorization**：只做界面设计，不改动无关画板。

## 规范选择（按优先级，首个命中即用）

| 优先级 | 触发 | 加载 |
|---|---|---|
| 1 | 移动端 App、iOS、Android、小程序、手机界面 | `references/guidelines-mobile-app.md` |
| 2 | 网站、落地页、官网、营销页、SaaS 产品站 | `references/guidelines-landing-page.md` |
| 3 | 表格、带表格的后台 | `references/guidelines-table.md` |
| 4 | Web App、设计系统、通用 UI（默认） | `references/guidelines-web-app.md` |

- **设计系统 / 组件库 / design token** 类任务以 `guidelines-web-app.md` 为基座，在库的层次上应用同一套组件、字体、色彩纪律：建立 token 集、组件状态、间距刻度。
- **图转 UI**（照着参考图还原界面）：走同样的规范，但把参考图当作布局与视觉的真相源，先忠实复现结构，再调整风格。

## 通用原则（适用于所有交付类型）

摘自 `guidelines-web-app.md`，是跨品类的结构性法则：

- **目的优先**：一个界面回答一个主导问题、支撑一个主动作。多个目标竞争就拆成不同界面，不做多目的杂糅界面。
- **主导区域**：每个界面必须有一个主导视觉区域，视觉权重反映重要性，次要区域从属。
- 视觉身份（字体、色彩、风格）由风格指南决定；本模块只管结构、认知、产品品质层面的法则。

## Process

1. 判断交付类型：先从用户描述和画板内容确定是移动端、网站、表格还是通用 Web App。
2. 按上表优先级选中唯一一份规范并加载。
3. 读规范里的结构法则（目的优先、主导区域），在动手前先确认每个界面的主目的与主动作。
4. 需要同时出代码时，叠加加载 design-to-code 模块的规则文件。
5. 完成后逐项核对：主操作唯一、主导区域明确、层级与间距符合所选规范。

## 与其他模块的关系

- 需要同时产代码时，叠加读 `modules/design-to-code` 的 `guidelines-code.md` 与 `guidelines-tailwind.md`。
- 画布读取与编辑调用见 `shared/mcp-cheatsheet.md`。
