# CDN Lighting Official Website Archive Tool

这个工具用于把 CDN Lighting 原官网内容下载到仓库中，作为后续重构英文官网时的素材库和资料备份。

默认抓取范围：

- 官网页面 HTML
- 产品分类页、产品详情页
- 项目案例页、新闻页、下载页
- 图片、CSS、JS 等静态资源
- 产品技术资料附件，例如 PDF、Word、Excel、ZIP、IES、LDT、RFA、DWG、DXF 等
- 抓取清单 `manifest.csv`
- 下载失败清单 `failed-urls.csv`

## 本地运行

在仓库根目录执行：

```bash
pip install -r tools/cdnlight_archive/requirements.txt
python tools/cdnlight_archive/crawl_cdnlight.py \
  --base https://www.cdnlight.com/ \
  --out cdnlight-official-archive \
  --max-pages 3000 \
  --delay 0.25 \
  --max-file-mb 95
```

输出目录：

```text
cdnlight-official-archive/
  site/               # HTML 页面
  assets/             # 图片、CSS、JS、字体、视频等
  product-files/      # 产品技术资料附件
  manifest.csv        # 成功下载清单
  failed-urls.csv     # 下载失败清单
```

## GitHub 仓库注意事项

GitHub 普通仓库不适合长期保存超大二进制文件。单文件超过 100MB 会无法提交，仓库整体过大也会影响后续 Pages 部署和拉取速度。

建议先执行一次抓取，检查 `manifest.csv` 和 `failed-urls.csv`。如果产品资料附件很多，可以把 PDF、IES、LDT、BIM 文件转存到单独仓库或对象存储中，当前仓库只保存索引和精选素材。

## 可能无法抓取的内容

以下内容可能会进入 `failed-urls.csv`：

- 需要登录后才能下载的附件
- 使用动态接口生成的一次性下载地址
- 文件过大，超过 `--max-file-mb` 限制
- 原站服务器拒绝或超时的资源

这类资源需要单独处理，例如增加登录 cookie、调低抓取速度，或手动补充下载。