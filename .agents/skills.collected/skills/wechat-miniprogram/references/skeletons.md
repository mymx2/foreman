# 页面骨架

骨架位于 `assets/skeletons/`，每个骨架由 `pages/<page>/` 页面文件和必要的 `utils/` 文件组成，不含 `app.json`、`project.config.json`。

## 选用

| 需求核心页面 | 骨架 |
|---|---|
| 一组条目，可新增、编辑、删除（待办、记账、打卡、通讯录） | `list-crud` |
| 填写信息后提交，再告知结果（报名、反馈、预约、信息登记） | `form-result` |
| 个人中心：头像昵称加功能入口列表（我的、设置、关于） | `profile` |

需求只有部分结构相同，取相同的部分。需求核心页面不在上表，按 [原生工程约束](native-project.md) 直接实现。工程里已有同类页面，修改已有页面。

## list-crud

文件：

- `pages/item-list/item-list.{wxml,wxss,js,json}`
- `utils/item-store.js`

页面内容：列表、右下角新增按钮、底部弹层表单（新增与编辑共用，含必填标题和可选备注）、删除二次确认、loading / empty / error（带重试）三态。

数据层 `createLocalItemStore({ storageKey })` 返回 `list`、`create`、`update`、`remove`。四个方法都返回 `{ data, error }`，不会 reject。

| 情形 | error |
|---|---|
| `update`、`remove` 命中 0 条 | `NOT_FOUND_OR_FORBIDDEN` |
| id 无效 | `INVALID_ID` |
| 没有可写字段 | `INVALID_PAYLOAD` |
| 存储读写异常 | `CLIENT_EXCEPTION` |

页面只调用这四个方法，不直接访问本地存储。方法签名和返回结构与 `cloud-service` 的 `miniprogram-data-access.js` 中 `createTableAccess` 返回的对象一致，数据上云时把页面里的 store 换成该对象，页面代码不变，步骤见 [小程序接入云数据](cloud-upgrade.md)。

按需求替换：字段、列表项展示文案、`storageKey`、页面标题。

## form-result

文件：

- `pages/submit-form/submit-form.{wxml,wxss,js,json}`
- `pages/submit-result/submit-result.{wxml,wxss,js,json}`

表单页：姓名（必填）、联系方式（必填）、说明（可选）。校验失败时在表单顶部给出原因并标出具体出错字段，提交中按钮禁用并显示 loading，成功后 `wx.redirectTo` 到结果页，失败留在原页并显示错误。

提交逻辑在页面方法 `submit(values)` 中，其中的替换点当前模拟成功，没有任何网络请求。替换为真实保存逻辑之前，提交结果不代表数据已保存到服务器。

结果页：按 query 的 `status` 显示成功或失败，非法值按失败处理，提供返回首页（`wx.reLaunch` 到 `/pages/index/index`）和继续提交两个入口。

按需求替换：字段与校验规则、结果页文案、返回首页的目标路径。

## profile

文件：

- `pages/profile/profile.{wxml,wxss,js,json}`

页面内容：顶部标题、头像与昵称简介卡片、分组功能入口列表。头像为昵称首字（按字符取，兼容 emoji），昵称为空时显示 `?`，昵称和简介为空时分别显示「未设置昵称」和默认简介文案。

资料来源在 `loadProfile()` 中，替换点当前返回空资料，没有任何网络请求和登录逻辑。页面不含头像昵称授权和 `wx.login`。

入口由 `data.menuGroups` 驱动，每组含 `key` 和 `items`，每个入口含 `key`、`text`、`path`。`handleMenuTap` 的行为：

| 情形 | 行为 |
|---|---|
| `path` 为空 | toast「该功能暂未接入」 |
| `path` 非空 | `wx.navigateTo`，失败时 toast「页面暂未开放」 |

按需求替换：`loadProfile()` 的资料来源、`menuGroups` 的入口与目标页面路径、页面标题。目标页面不存在时保留空 `path` 或补建对应页面。

## 接入步骤

1. 确认工程源码根目录，已有页面不覆盖。
2. 读取骨架资产原文，把 `pages/<page>/` 复制到工程同名位置，`utils/` 文件复制到工程 `utils/`。
3. 把新页面路径加入 `app.json` 的 `pages`，调整首页入口，保留已有配置（含 `lazyCodeLoading`）。
4. 按上面"按需求替换"修改。
5. 保存后修复已报告的原生校验问题。

## 边界

- 骨架页面不含登录、云请求、手写网络请求；需要时按 `cloud-service`。
- 只保留用户需要的字段和页面。
