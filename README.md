# enz_ReaperTools - REAPER 插件

## 功能列表

### enz_Toggle visibility of muted tracks
切换静音轨道的显示/隐藏状态。如果当前有静音轨道可见，就隐藏所有静音轨道；如果没有，就显示所有轨道。

### enz_Toggle float for selected track FX  
智能切换所选轨道FX插件的悬浮窗口。如果大部分FX悬浮窗口关闭就全部打开，否则全部关闭。

### ENZ UCS Auto Rename Selected Items
使用中文自然语言描述，为选中的音频 Item 生成 UCS 官方 CatID 前缀、英文 FXName 和序列号，并批量写入 take name。首版为 Windows 优先，需要先启动本地 `enz_ucs_service.exe`。

## 安装方法

### 🚀 方法1：ReaPack 自动安装（推荐）
1. 在 REAPER 中安装 ReaPack 扩展
2. 打开 **Extensions** → **ReaPack** → **Manage repositories**
3. 点击 **Import repositories**
4. 添加仓库地址：`https://raw.githubusercontent.com/signorzhao/reapack_repo/main/index.xml`
5. 搜索 "enz_ReaperTools" 并安装
6. 如需 UCS 重命名工具，搜索 "enz_UCS_Auto_Rename_Selected_Items.lua" 并安装

### 方法2：从 GitHub Releases 下载
- **Windows**: [reaper_enz_ReaperTools.dll](https://github.com/signorzhao/reaper-plugin-dev/releases/latest/download/reaper_enz_ReaperTools.dll)
- **macOS**: [reaper_enz_ReaperTools.dylib](https://github.com/signorzhao/reaper-plugin-dev/releases/latest/download/reaper_enz_ReaperTools.dylib)
- **UCS 后端 Windows 服务**: [enz_ucs_service.exe](https://github.com/signorzhao/reaper-plugin-dev/releases/latest/download/enz_ucs_service.exe)

### 安装步骤
- **Windows**: 将 `reaper_enz_ReaperTools.dll` 复制到 `%APPDATA%\REAPER\UserPlugins\`
- **macOS**: 将 `reaper_enz_ReaperTools.dylib` 复制到 `~/Library/Application Support/REAPER/UserPlugins/`
- 重启 REAPER

## 自动构建和发布
- ✅ 自动构建 Windows / macOS 插件
- ✅ 自动构建 Windows UCS 本地服务
- ✅ 自动创建 GitHub Release
- ✅ 自动更新 ReaPack 索引
- ✅ 支持一键订阅更新

## 开发信息
- 使用 CMake 构建系统
- 支持跨平台编译
- 集成 GitHub Actions CI/CD
- 支持 ReaPack 分发

详细订阅说明请查看 [REAPACK.md](REAPACK.md)
