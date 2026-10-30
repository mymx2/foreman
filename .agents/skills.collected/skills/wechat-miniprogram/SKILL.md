---
name: wechat-miniprogram
description: "WeChat Mini Program (微信小程序) development framework. Use when building WeChat mini apps with WXML templates, WXSS styles, WXS scripting, component development, WeChat API integration, cloud development (云开发), and Mini Program lifecycle/performance optimization. 不适用于 Skyline 渲染引擎专项、glass-easel 组件框架或 TDesign 组件库问题（用对应专门技能）。"
description_zh: "微信小程序开发框架（模板、组件、API、云开发）"
description_en: "WeChat Mini Program framework (templates, components, APIs, cloud)"
version: 1.0.0
homepage: https://developers.weixin.qq.com/miniprogram/dev/framework/
allowed-tools: Read,Write,Bash
---

# WeChat Mini Program Skill

WeChat Mini Program (微信小程序) development framework skill, generated from official documentation.

## Outcome Contract

- **Outcome**: 完成微信小程序的页面/组件/API 开发、云开发接入或性能优化，产出可运行的原生工程代码。
- **Done when**: 页面结构（wxml/wxss/js/json）齐全、在 `app.json` 注册、通过原生工程约束校验；骨架接入时三态（loading/empty/error）完整。
- **Evidence**: `references/native-project.md` 约束逐项满足；骨架接入见 `references/skeletons.md` 步骤。
- **Authorization**: 不强制改写已有工程布局与技术栈；已有同类页面优先修改而非新建。

## When to Use This Skill

This skill should be triggered when:

- Developing WeChat Mini Programs (微信小程序)
- Working with WXML, WXSS, or WXS
- Using WeChat Mini Program APIs
- Building WeChat components
- Implementing WeChat open capabilities (开放能力)
- Debugging Mini Program issues
- Optimizing Mini Program performance

## Quick Reference

常用工程结构与代码模式速查。

### Project Structure

```
├── app.js          # App logic
├── app.json        # App configuration
├── app.wxss        # Global styles
├── pages/
│   └── index/
│       ├── index.js    # Page logic
│       ├── index.json  # Page configuration
│       ├── index.wxml  # Page template
│       └── index.wxss  # Page styles
└── components/     # Custom components
```

### Common Patterns

**Example 1** (javascript):

```javascript
WeixinJSBridge.invoke('imagePreview', {
    current: 'http://inews.gtimg.com/newsapp_bt/0/1693121381/641',
    urls: [ // 所有图片的URL列表，数组格式
        'https://img1.gtimg.com/10/1048/104857/10485731_980x1200_0.jpg',
        'https://img1.gtimg.com/10/1048/104857/10485726_980x1200_0.jpg',
        'https://img1.gtimg.com/10/1048/104857/10485729_980x1200_0.jpg'
    ]
}, function(res) {
    console.log(res.err_msg)
})
```

**Example 2** (javascript):

```javascript
wx.previewImage({
  current: 'https://img1.gtimg.com/10/1048/104857/10485726_980x1200_0.jpg',
  urls: [ // 所有图片的URL列表，数组格式
    'https://img1.gtimg.com/10/1048/104857/10485731_980x1200_0.jpg',
    'https://img1.gtimg.com/10/1048/104857/10485726_980x1200_0.jpg',
    'https://img1.gtimg.com/10/1048/104857/10485729_980x1200_0.jpg'
  ],
  success: function(res) {
    console.log(res)
  }
})
```

**Example 3** (html):

```html
<!-- /components/index.wmxl -->
<view class="index">{{prop}}</view>
```

**Example 4** (js):

```js
// /components/index.js
Component({
  properties: {
    prop: {
      type: String,
      value: 'index.properties'
    },
  },
})
```

**Example 5** (css):

```css
/* /components/index.wxss */
.index {
  color: green;
}
```

**Example 6** (json):

```json
{
  "nickName": "Band",
  "gender": 1,
  "language": "zh_CN",
  "city": "Guangzhou",
  "province": "Guangdong",
  "country": "CN",
  "avatarUrl": "http://wx.qlogo.cn/mmopen/vi_32/1vZvI39NWFQ9XM4LtQpFrQJ1xlgZxx3w7bQxKARol6503Iuswjjn6nIGBiaycAjAtpujxyzYsrztuuICqIM5ibXQ/0"
}
```

**Example 7** (json):

```json
{
    "openId": "OPENID",
    "nickName": "NICKNAME",
    "gender": GENDER,
    "city": "CITY",
    "province": "PROVINCE",
    "country": "COUNTRY",
    "avatarUrl": "AVATARURL",
    "unionId": "UNIONID",
    "watermark":
    {
        "appid":"APPID",
        "timestamp":TIMESTAMP
    }
}
```

**Example 8** (js):

```js
wx.cloud.callFunction({
  name: 'myFunction',
  data: {
    weRunData: wx.cloud.CloudID('xxx'), // 这个 CloudID 值到云函数端会被替换
    obj: {
      shareInfo: wx.cloud.CloudID('yyy'), // 非顶层字段的 CloudID 不会被替换，会原样字符串展示
    }
  }
})
```

**Example 9** (html):

```html
<scroll-view type="list" scroll-y>
  <view> a </view>
  <view> b </view>
  <view> c </view>
</scroll-view>
```

**Example 10** (html):

```html
<scroll-view type="list" scroll-y>
  <virtual-comp>
    <view> a </view>
    <view> b </view>
    <view> c </view>
  </virtual-comp>
</scroll-view>
```


## Reference Files

This skill includes comprehensive documentation in `references/`:

- **getting_started.md** - Quick start and introduction
- **framework.md** - Mini Program framework (逻辑层、视图层)
- **components.md** - Built-in components
- **api.md** - API reference
- **cloud.md** - Cloud development (云开发)
- **reference.md** - Configuration reference
- **native-project.md** - 原生工程约束（JSON 严格性、WXML 表达式限制、lazyCodeLoading、路径与大小写规则）
- **skeletons.md** - 页面骨架选用与接入步骤（list-crud / form-result / profile 三套生产级骨架）

Use `view` to read specific reference files when detailed information is needed.

## Page Skeletons

生产级页面骨架位于 `assets/skeletons/`，平台无关、可直接复制到工程使用：

- **list-crud** — 列表 + 新增/编辑/删除（待办、记账、打卡），含底部弹层表单与 loading/empty/error 三态，统一 `{data, error}` 数据层（`utils/item-store.js`）
- **form-result** — 表单提交 + 结果页（报名、反馈、预约），含字段校验、提交中禁用、成功 redirectTo
- **profile** — 个人中心（头像昵称 + 分组功能入口列表），含空态兜底与 menuGroups 驱动

选用与接入步骤见 `references/skeletons.md`；工程约束见 `references/native-project.md`。骨架不含 `app.json`/`project.config.json`，接入时需自行注册页面路径。

### 骨架接入流程

1. 确认工程源码根目录，已有同名页面不覆盖。
2. 把骨架的 `pages/<page>/` 复制到工程同名位置，`utils/` 文件复制到工程 `utils/`。
3. 把新页面路径加入 `app.json` 的 `pages`，保留已有配置（含 `lazyCodeLoading`）。
4. 按 `references/skeletons.md` 的"按需求替换"逐项改字段、文案、`storageKey`、目标路径。
5. 按 `references/native-project.md` 校验 JSON 严格性、WXML 表达式、路径大小写，修复全部报告问题。

## Key Concepts

小程序核心概念与生命周期。

### App Lifecycle

```javascript
App({
  onLaunch(options) {
    // Mini Program initialized
  },
  onShow(options) {
    // Mini Program shown
  },
  onHide() {
    // Mini Program hidden
  },
  globalData: {
    userInfo: null
  }
})
```

### Page Lifecycle

```javascript
Page({
  data: {
    message: 'Hello World'
  },
  onLoad(options) {
    // Page loaded
  },
  onShow() {
    // Page shown
  },
  onReady() {
    // Page ready
  },
  onHide() {
    // Page hidden
  },
  onUnload() {
    // Page unloaded
  }
})
```

### WXML Data Binding

```wxml
<view>{{message}}</view>
<view wx:if="{{condition}}">Conditional</view>
<view wx:for="{{array}}" wx:key="id">{{item}}</view>
```

### Event Handling

```wxml
<button bindtap="handleTap">Click Me</button>
```

```javascript
Page({
  handleTap(e) {
    console.log(e)
  }
})
```

## Working with This Skill

按熟悉程度与任务类型选择入口。

### For Beginners
Start with the getting_started reference file for foundational concepts.

### For Specific Features
Use the appropriate category reference file (api, framework, etc.) for detailed information.

### For Code Examples
The quick reference section above contains common patterns extracted from the official docs.

## Resources

- [Official Documentation](https://developers.weixin.qq.com/miniprogram/dev/framework/)
- [Component Library](https://developers.weixin.qq.com/miniprogram/dev/component/)
- [API Reference](https://developers.weixin.qq.com/miniprogram/dev/api/)

## Notes

- This skill was automatically generated from official WeChat documentation
- Reference files preserve the structure and examples from source docs
- Content is in Chinese as per official documentation
