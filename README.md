# enz_ReaperTools - REAPER 插件

## 功能列表

### enz_Toggle visibility of muted tracks
切换静音轨道的显示/隐藏状态。如果当前有静音轨道可见，就隐藏所有静音轨道；如果没有，就显示所有轨道。

### enz_Toggle float for selected track FX  
智能切换所选轨道FX插件的悬浮窗口。如果大部分FX悬浮窗口关闭就全部打开，否则全部关闭。

## 安装方法

### 方法1：直接下载（推荐）
访问我们的下载页面：https://signorzhao.github.io/reaper-plugin-project/

### 方法2：从 GitHub Releases 下载
- **Windows**: [reaper_enz_ReaperTools.dll](https://github.com/signorzhao/reaper-plugin-project/releases/latest/download/reaper_enz_ReaperTools.dll)
- **macOS**: [reaper_enz_ReaperTools.dylib](https://github.com/signorzhao/reaper-plugin-project/releases/latest/download/reaper_enz_ReaperTools.dylib)

### 方法3：通过 ReaPack 自动安装
1. 在 REAPER 中安装 ReaPack 扩展
2. 打开 Actions → ReaPack → Browse packages
3. 点击 "Import repositories"
4. 添加仓库地址：`https://raw.githubusercontent.com/signorzhao/reaper-plugin-project/main/reaper_plugin_list.xml`
5. 搜索 "enz_ReaperTools" 并安装

**注意**: 如果遇到网络连接问题，请使用方法1或方法2。

### 安装步骤
- **Windows**: 将 `reaper_enz_ReaperTools.dll` 复制到 `%APPDATA%\REAPER\UserPlugins\`
- **macOS**: 将 `reaper_enz_ReaperTools.dylib` 复制到 `~/Library/Application Support/REAPER/UserPlugins/`
- 重启 REAPER

## 自动构建
每次发布新版本时，GitHub Actions 会自动编译 Windows 和 macOS 平台的插件文件。

