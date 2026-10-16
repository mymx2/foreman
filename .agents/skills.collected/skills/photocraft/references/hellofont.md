# 字由（hellofont.cn）字体获取

官网 `/font-list` 是 Vue SPA，字体数据不在 HTML 里。三个通道分工：

| 通道 | 内容 | 能否拿到字体文件 |
| --- | --- | --- |
| 目录检索 API（back3.hellofont.cn） | 字体名、家族、版本、文件名、授权标签、预览图 | 否 |
| webfont 预览（hellowebfont.com / resource.hellofont.cn） | 只含展示字符的子集，供网页渲染 | 否 |
| 字由桌面客户端 | 按账号授权下载并激活 ttf/otf | 是（唯一正规路径） |

## 目录检索接口

`scripts/hellofont-search.py` 封装了此接口，直接运行它即可；手工复现时：

```
POST https://back3.hellofont.cn/FontDistributionManagement/api/FontSearch/GetFontSearchItem
Content-Type: application/json
appid: <APPID>
sign: <md5>
timestamp: <毫秒时间戳>

{"pageNum": 0, "pageSize": 20, "orderTag": 0, "searchKey": "站酷", "fontTagIdList": [73]}
```

签名：`sign = md5(SECRET + "appid=" + APPID + "&method=GetFontSearchItem&timestamp=" + timestamp + SECRET)`。
APPID/SECRET 是官网前端 `all.js` 里 `u.ajax` header 构造处的公开值，非用户凭据；接口若失效，到
`https://www.hellofont.cn/dist/all.js` 的 `header:function` 处重新核对，或用环境变量
`HELLOFONT_APPID` / `HELLOFONT_SECRET` 覆盖。

注意：`fontTagIdList` 传空数组或空串时服务端只回 `{"TimeStamp": ...}` 且无错误；要么给真实标签
id，要么整个字段连同关键词一起省略语义（关键词可为空串但字段需在）。

响应（`SearchCount` / `totalCount` 为总数）：

| 字段 | 含义 |
| --- | --- |
| `id` | 字体 id，详情页 `https://www.hellofont.cn/font-detail?fontid=<id>` |
| `ProductName` / `ProductSetName` | 字体名 / 家族名（家族多于 1 款时对外显示家族名） |
| `ProductFileName` | 落盘文件名（如 `站酷酷黑.ttf`），仅作识别 |
| `Version` / `FamilyCount` / `ApplyHot` | 版本 / 家族字数 / 热度 |
| `IsFree` / `IsMemberFont` | 免费 / 会员字体标记，都没有则需单独或商业授权 |
| `PreviewFileUrl` | PNG/JPG 预览图，不是字体 |

## 标签 id 速查

授权范围（互斥筛选常用）：

| id | 含义 |
| --- | --- |
| 73 | 免费商用 |
| 105 | 会员商用 |
| 177 | 单款商用 |
| 106 | 单独授权 |
| 179 | 企业专享 |

常用分类：15 黑体、20 宋体、17 楷体、22 圆体、54 仿宋、36 手写风、37 书法体、51 创意字体、
151 彩色字体；字重 86–90（纤细→超粗）；字符集 78 常规 / 79 超大 / 80 小 / 9 繁体 / 158 BIG5；
语言 10 简体、7 英文、8 日文、101 韩文。全部映射来自 `/font-list` 页面 `data-id`。

## 字体文件的获取路径

网页的「激活 / 下载」按钮不给 ttf 直链，只做两件事：唤起字由桌面客户端，或引导下载客户端。

- 有客户端：网页 `POST http://localhost:59527/add?uid=<用户guid>&fid=<字体id>&private=<0|1>`
  让客户端下载并激活字体（`remove` 反激活；`call?operation=show` 唤起主界面）。客户端未响应时
  回退 `hellofont://` URL scheme。字体文件由客户端按账号授权落地并注入系统。
- 无客户端：`https://www.hellofont.cn/download` 下载客户端安装，登录后在客户端或网页点激活。
- 免费商用（73）字体同样经客户端激活；授权条款以字体详情页为准。

对 PhotoCraft 的衔接：字体激活/安装进系统后，`type.fonts` 能列出、文字图层的 `text.font`
可直接引用（字体名以 `type.fonts` 返回为准，不是 `ProductFileName`）。

## 红线

- 只走客户端激活、官方下载或明确开源授权的渠道拿字体文件；不写、不跑绕过授权的抓取。
- 「免费商用」不等于无条件使用，产出物对外前核对详情页授权条款。
- 目录接口签名参数是复现官网查询用的公开值，不用于批量抓库、分发或转售。
