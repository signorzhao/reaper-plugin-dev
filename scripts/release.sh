#!/bin/bash

# 发布脚本 - 自动更新版本号和创建发布

if [ $# -eq 0 ]; then
    echo "用法: $0 <版本号>"
    echo "例如: $0 1.0.1"
    exit 1
fi

VERSION=$1

echo "开始发布版本 $VERSION..."

# 更新 reaper_plugin_list.txt 中的版本号
sed -i.bak "s/version: [0-9.]*/version: $VERSION/g" reaper_plugin_list.txt
sed -i.bak "s/url:.*\/v[0-9.]*/url: https:\/\/github.com\/signorzhao\/reaper-plugin-project\/releases\/download\/v$VERSION/g" reaper_plugin_list.txt

# 更新 README.md 中的版本号（如果有的话）
# sed -i.bak "s/版本 [0-9.]*/版本 $VERSION/g" README.md

# 提交更改
git add reaper_plugin_list.txt README.md
git commit -m "Release version $VERSION"

# 创建标签
git tag -a "v$VERSION" -m "Release version $VERSION"

# 推送更改和标签
git push origin main
git push origin "v$VERSION"

echo "版本 $VERSION 发布完成！"
echo "GitHub Actions 将自动构建并创建发布。" 