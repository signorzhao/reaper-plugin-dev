import xml.etree.ElementTree as ET
import os
from datetime import datetime

# 获取版本号（从 tag 中提取，例如 v1.0.0 -> 1.0.0）
version = os.getenv("GITHUB_REF_NAME", "1.0.0")
if version.startswith('v'):
    version = version[1:]

# 插件文件名
win_file = "reaper_enz_ReaperTools.dll"
mac_file = "reaper_enz_ReaperTools.dylib"

# 构建下载 URL
repo = os.getenv("GITHUB_REPOSITORY", "signorzhao/reaper-plugin-repo")
tag = os.getenv("GITHUB_REF_NAME", "v1.0.0")
url_win = f"https://github.com/{repo}/releases/download/{tag}/{win_file}"
url_mac = f"https://github.com/{repo}/releases/download/{tag}/{mac_file}"

# ReaPack index 文件路径
index_file = "reapack/index.xml"

# 创建 XML 结构
root = ET.Element("reapack", version="1", xmlns="http://reapack.com/repository", xmlns_reapack="http://reapack.com/repository")
category = ET.SubElement(root, "category", name="Plugins")
plugin = ET.SubElement(category, "reapack:reaperplugin",
                      name="enz_ReaperTools",
                      version=version,
                      desc="Toggle visibility of muted tracks",
                      date=datetime.now().strftime("%Y-%m-%d"),
                      author="enz",
                      type="effect")

# 添加平台特定的下载链接
ET.SubElement(plugin, "source", file=url_win, platform="win64")
ET.SubElement(plugin, "source", file=url_mac, platform="osx64")

# 确保目录存在
os.makedirs("reapack", exist_ok=True)

# 写入文件
tree = ET.ElementTree(root)
tree.write(index_file, encoding="utf-8", xml_declaration=True)

print(f"Updated ReaPack index for version {version}")
print(f"Windows: {url_win}")
print(f"macOS: {url_mac}") 