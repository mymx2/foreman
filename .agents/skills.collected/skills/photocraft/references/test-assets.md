# 测试素材与占位图

实际效果测试需要不同尺寸图片时，用 `scripts/fetch-asset.py`（运行它）按需落盘。限额、路由等数字以各来源官方文档与脚本 `--help` 为准。

## 来源与分工

| 来源 | 承接 | Key | 定位 |
| --- | --- | --- | --- |
| devimg.cn（`cdn.devimg.cn`） | 占位图、照片、头像、骨架、场景、码形 | 免 | 主源，`--seed` 钉结果 |
| picsum.photos | 照片 | 免 | 备选，devimg 长期不可用时用 |
| placehold.co | 合成色块 | 免 | 备选，同上 |
| Pexels（`api.pexels.com`） | 真实照片 | `PEXELS_API_KEY` | 需要真图质感/可商用成品素材时用 |
| Pixabay（`pixabay.com/api`） | 真实照片、矢量插画 | `PIXABAY_API_KEY` | 同上，限流更宽且含矢量/插画（制图元素） |

不引入其他占位服务（via.placeholder、dummyimage、loremflickr 等）；新需求先看 devimg 是否覆盖。Unsplash 不接 API：其条款要求热链 CDN URL、每次下载回调统计端点、展示面强制署名，与"下载文件进稿"的用法冲突；要它的图就人工去网页挑（网页下载不受 API 条款约束）。

## 规则

- **确定性**：进测试脚本、复现案例、对比基线的 devimg/picsum 图片一律带 `--seed`（picsum 也可用 `/id/`），同参数恒同图；不带 seed 的随机结果只用于一次性调试。Pexels/Pixabay 接口不接受 seed，用返回的 content id / source_page 记录来源。
- **尺寸**：位图由脚本按目标尺寸中心裁切（需 Pillow，缺失时保留原图并在报告里注明）；SVG 不缩放。报告含 `wanted`、`actual` 与 `resized`。
- **占位类只用于测试**：devimg/picsum/placehold 的图不进生产成品；成品素材用 Pexels 等真实图库。
- **限额**：devimg 栅格 60 次/分/IP、SVG/JSON 1000 次/分/IP，超限 429；Pexels 200 次/时、2 万/月（响应头 `X-Ratelimit-*` 可查余额）；Pixabay 约 100 次/分（同名响应头）。三家都禁止批量抓取与压测，单次任务按需取图，不铺量。
- **devimg 细则**（上游规范浓缩）：尺寸 10–4000px，位图走 `.png`/`.webp` 后缀或 `?format=`；照片 `scene` 15 种（product/food/news/…）无 seed 时随机且缓存仅 60s；伪码不可扫描，禁用于支付/登录/物流真码场景。完整路由以 devimg 官方文档与 `fetch-asset.py --help` 为准。

## Pexels 要点

- 注册：pexels.com/api 免费申请 Key，请求带 `Authorization: <key>` 头；Key 只放环境变量 `PEXELS_API_KEY`，不进命令行、不进仓。
- 搜索：`GET https://api.pexels.com/v1/search?query=<词>&per_page=1&orientation=landscape|portrait|square`；照片 `src` 给 original/large2x/large/medium/small/portrait/landscape/tiny 固定档位，`fetch-asset.py --variant` 选档。
- 授权（Pexels License）：免费可商用、可修改、无需署名；不得原样转售、不得暗示代言、涉及可识别人物/商标的负面使用受限。API 展示面按官方指南给显眼 Pexels 链接或署名摄影师。（license 页反爬 403，条款据官方 API 文档与公开转述，商用前以 pexels.com/license 为准）
- 图片落在本地后不回传、不转售；留下载记录（fetch-asset 报告里的 photographer/source_page）备查。

## Pixabay 要点

- Key 在 pixabay.com/api/docs 登录后获取，走查询参数 `?key=`（脚本读环境变量 `PIXABAY_API_KEY`）。
- 搜索：`GET https://pixabay.com/api/?q=<词>&image_type=photo|illustration|vector&per_page=3`；命中项 `largeImageURL`（≤1280px）是常规可用档，`vectorURL` 只在完整 API 权限下给矢量原件。
- 授权（Pixabay Content License）：免费可商用、可修改、无需署名；不得原样转售、不得贬损性使用；展示搜索结果时标注来源（脚本报告带 source_page/user）。
- 官方要求结果缓存 24 小时、仅人工驱动请求；单次任务按需取图不铺量。

## 追踪

- 占位规范：各来源官方文档；脚本路由用 `python scripts/fetch-asset.py --help` 查看
- devimg：[快速开始](https://devimg.cn/guide/quick-start.html)、[功能一览](https://devimg.cn/guide/dev-spec.html)、[使用规范](https://devimg.cn/guide/fair-use.html)
- Pexels：[API 文档](https://www.pexels.com/api/documentation/)、[许可](https://www.pexels.com/license/)
- Pixabay：[API 文档](https://pixabay.com/api/docs/)、[Content License](https://pixabay.com/service/license-summary/)
