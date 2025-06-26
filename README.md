# enz_ReaperTools - REAPER 插件

## 功能列表

### enz_Toggle visibility of muted tracks
切换静音轨道的显示/隐藏状态。如果当前有静音轨道可见，就隐藏所有静音轨道；如果没有，就显示所有轨道。

### enz_Toggle float for selected track FX  
智能切换所选轨道FX插件的悬浮窗口。如果大部分FX悬浮窗口关闭就全部打开，否则全部关闭。

## 安装方法

### 🚀 方法1：ReaPack 自动安装（推荐）
1. 在 REAPER 中安装 ReaPack 扩展
2. 打开 **Extensions** → **ReaPack** → **Manage repositories**
3. 点击 **Import repositories**
4. 添加仓库地址：`https://signorzhao.github.io/reaper-plugin-repo/reapack/index.xml`
5. 搜索 "enz_ReaperTools" 并安装

### 方法2：从 GitHub Releases 下载
- **Windows**: [reaper_enz_ReaperTools.dll](https://github.com/signorzhao/reaper-plugin-repo/releases/latest/download/reaper_enz_ReaperTools.dll)
- **macOS**: [reaper_enz_ReaperTools.dylib](https://github.com/signorzhao/reaper-plugin-repo/releases/latest/download/reaper_enz_ReaperTools.dylib)

### 安装步骤
- **Windows**: 将 `reaper_enz_ReaperTools.dll` 复制到 `%APPDATA%\REAPER\UserPlugins\`
- **macOS**: 将 `reaper_enz_ReaperTools.dylib` 复制到 `~/Library/Application Support/REAPER/UserPlugins/`
- 重启 REAPER

## 自动构建和发布
- ✅ 自动构建 Windows / macOS 插件
- ✅ 自动创建 GitHub Release
- ✅ 自动更新 ReaPack 索引
- ✅ 支持一键订阅更新

## 开发信息
- 使用 CMake 构建系统
- 支持跨平台编译
- 集成 GitHub Actions CI/CD
- 支持 ReaPack 分发

详细订阅说明请查看 [REAPACK.md](REAPACK.md)

