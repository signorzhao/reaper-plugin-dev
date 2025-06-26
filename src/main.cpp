#include "reaper_plugin.h"

// Define pointers for REAPER API functions
void (*ShowConsoleMsg)(const char *msg);
int (*CountTracks)(ReaProject* proj);
MediaTrack* (*GetTrack)(ReaProject* proj, int trackidx);
double (*GetMediaTrackInfo_Value)(MediaTrack* track, const char* parmname);
bool (*SetMediaTrackInfo_Value)(MediaTrack* track, const char* parmname, double newvalue);
void (*TrackList_AdjustWindows)(bool isMcp);
void (*Undo_BeginBlock)();
void (*Undo_EndBlock)(const char* desc, int extra_flags);
int (*plugin_register)(const char* name, void* infostruct);
int (*CountTrackMediaItems)(MediaTrack* track);
MediaItem* (*GetTrackMediaItem)(MediaTrack* track, int itemidx);
double (*GetMediaItemInfo_Value)(MediaItem* item, const char* parmname);
void (*TrackFX_SetOpen)(MediaTrack* track, int fx, bool open);
void (*TrackFX_Show)(MediaTrack* track, int fx, int show);

// === 新增API指针 ===
MediaTrack* (*GetSelectedTrack)(ReaProject* proj, int seltrackidx);
int (*TrackFX_GetCount)(MediaTrack* track);
bool (*TrackFX_GetEnabled)(MediaTrack* track, int fx);
int (*TrackFX_GetParamFromIdent)(MediaTrack* track, int fx, const char* ident_str);
double (*TrackFX_GetParam)(MediaTrack* track, int fx, int param, double* minval, double* maxval);
bool (*TrackFX_GetOffline)(MediaTrack* track, int fx);
bool (*TrackFX_GetOpen)(MediaTrack* track, int fx);
void* (*TrackFX_GetFloatingWindow)(MediaTrack* track, int fx);

// Global variable for our command ID
static int enz_toggleMutedTracksCmdId = 0;
static int enz_toggleSelectedTrackFXFloatCmdId = 0;

// Helper function to check if all items on a track are muted
bool AllItemsAreMuted(MediaTrack* track)
{
    const int num_items = CountTrackMediaItems(track);
    if (num_items == 0)
    {
        return false; // A track with no items isn't considered "all items muted"
    }

    for (int i = 0; i < num_items; i++)
    {
        MediaItem* item = GetTrackMediaItem(track, i);
        if (GetMediaItemInfo_Value(item, "B_MUTE") == 0.0) // Found at least one unmuted item
        {
            return false;
        }
    }

    return true; // All items were muted
}

// Helper function to determine if a track should be considered muted
bool IsTrackEffectivelyMuted(MediaTrack* track)
{
    // Check if the track itself is muted
    if (GetMediaTrackInfo_Value(track, "B_MUTE") > 0.0)
    {
        return true;
    }
    // Otherwise, check if all of its items are muted
    return AllItemsAreMuted(track);
}

void ToggleMutedTracksVisibility()
{
    // First, determine if we should hide or show tracks.
    // Scan for any visible, "effectively muted" tracks.
    bool muted_tracks_are_visible = false;
    const int num_tracks = CountTracks(nullptr);
    for (int i = 0; i < num_tracks; i++)
    {
        MediaTrack* track = GetTrack(nullptr, i);
        if (GetMediaTrackInfo_Value(track, "B_SHOWINTCP") > 0.0 && IsTrackEffectivelyMuted(track))
        {
            muted_tracks_are_visible = true;
            break;
        }
    }

    Undo_BeginBlock();

    if (muted_tracks_are_visible)
    {
        // Action: Hide all effectively muted tracks
        for (int i = 0; i < num_tracks; i++)
        {
            MediaTrack* track = GetTrack(nullptr, i);
            if (IsTrackEffectivelyMuted(track))
            {
                SetMediaTrackInfo_Value(track, "B_SHOWINTCP", 0.0);
                SetMediaTrackInfo_Value(track, "B_SHOWINMIXER", 0.0);
            }
        }
    }
    else
    {
        // Action: Show all tracks
        for (int i = 0; i < num_tracks; i++)
        {
            MediaTrack* track = GetTrack(nullptr, i);
            SetMediaTrackInfo_Value(track, "B_SHOWINTCP", 1.0);
            SetMediaTrackInfo_Value(track, "B_SHOWINMIXER", 1.0);
        }
    }

    Undo_EndBlock("enz_Toggle visibility of muted tracks", -1);
    TrackList_AdjustWindows(true); // Update both TCP and MCP
}

// === 新功能实现 ===
// 智能切换：如果大部分FX悬浮窗口是关闭的，就全部打开；如果大部分是打开的，就全部关闭
void Enz_ToggleSelectedTrackFXFloat(bool force_open)
{
    Undo_BeginBlock();
    
    // 如果force_open为true，直接全部打开
    if (force_open) {
        int sel_idx = 0;
        MediaTrack* track = nullptr;
        while ((track = GetSelectedTrack(nullptr, sel_idx++))) {
            int fx_count = TrackFX_GetCount(track);
            for (int fx = 0; fx < fx_count; ++fx) {
                // 只处理启用且未bypass且未offline的FX
                if (!TrackFX_GetEnabled(track, fx)) continue;
                if (TrackFX_GetOffline && TrackFX_GetOffline(track, fx)) continue;
                int bypass_param = TrackFX_GetParamFromIdent(track, fx, ":bypass");
                if (bypass_param >= 0) {
                    double minv=0, maxv=0;
                    double val = TrackFX_GetParam(track, fx, bypass_param, &minv, &maxv);
                    if (val >= 0.5) continue; // bypass状态跳过
                }
                // 打开悬浮窗口
                TrackFX_Show(track, fx, 3); // showflag=3 for show floating window
            }
        }
    } else {
        // 智能切换：统计当前悬浮窗口状态，决定是全部打开还是全部关闭
        int total_valid_fx = 0;
        int open_fx_count = 0;
        
        // 第一遍：统计有效FX数量和已打开的悬浮窗口数量
        int sel_idx = 0;
        MediaTrack* track = nullptr;
        while ((track = GetSelectedTrack(nullptr, sel_idx++))) {
            int fx_count = TrackFX_GetCount(track);
            for (int fx = 0; fx < fx_count; ++fx) {
                // 只处理启用且未bypass且未offline的FX
                if (!TrackFX_GetEnabled(track, fx)) continue;
                if (TrackFX_GetOffline && TrackFX_GetOffline(track, fx)) continue;
                int bypass_param = TrackFX_GetParamFromIdent(track, fx, ":bypass");
                if (bypass_param >= 0) {
                    double minv=0, maxv=0;
                    double val = TrackFX_GetParam(track, fx, bypass_param, &minv, &maxv);
                    if (val >= 0.5) continue; // bypass状态跳过
                }
                
                total_valid_fx++;
                // 检查悬浮窗口是否已打开（通过检查是否有float window）
                if (TrackFX_GetFloatingWindow && TrackFX_GetFloatingWindow(track, fx)) {
                    open_fx_count++;
                }
            }
        }
        
        // 决定操作：如果大部分是关闭的，就全部打开；否则全部关闭
        bool should_open = (open_fx_count * 2 < total_valid_fx); // 如果打开的少于一半，就全部打开
        
        // 第二遍：执行操作
        sel_idx = 0;
        track = nullptr;
        while ((track = GetSelectedTrack(nullptr, sel_idx++))) {
            int fx_count = TrackFX_GetCount(track);
            for (int fx = 0; fx < fx_count; ++fx) {
                // 只处理启用且未bypass且未offline的FX
                if (!TrackFX_GetEnabled(track, fx)) continue;
                if (TrackFX_GetOffline && TrackFX_GetOffline(track, fx)) continue;
                int bypass_param = TrackFX_GetParamFromIdent(track, fx, ":bypass");
                if (bypass_param >= 0) {
                    double minv=0, maxv=0;
                    double val = TrackFX_GetParam(track, fx, bypass_param, &minv, &maxv);
                    if (val >= 0.5) continue; // bypass状态跳过
                }
                
                if (should_open) {
                    TrackFX_Show(track, fx, 3); // showflag=3 for show floating window
                } else {
                    // 尝试多种方法关闭悬浮窗口
                    TrackFX_Show(track, fx, 2); // 方法1: showflag=2
                    TrackFX_SetOpen(track, fx, false); // 方法2: 关闭所有窗口
                }
            }
        }
    }
    
    Undo_EndBlock("enz_Toggle float for selected track FX", -1);
}

// Hook function that REAPER calls for our action
static bool hook_command(int commandId, int flag)
{
    if (commandId == enz_toggleMutedTracksCmdId)
    {
        ToggleMutedTracksVisibility();
        return true;
    }
    if (commandId == enz_toggleSelectedTrackFXFloatCmdId)
    {
        // 智能切换：根据当前状态决定全部打开或全部关闭
        Enz_ToggleSelectedTrackFXFloat(false);
        return true;
    }
    return false;
}

extern "C"
{
REAPER_PLUGIN_DLL_EXPORT int REAPER_PLUGIN_ENTRYPOINT(REAPER_PLUGIN_HINSTANCE hInstance, reaper_plugin_info_t *rec)
{
    if (rec)
    {
        if (rec->caller_version != REAPER_PLUGIN_VERSION || !rec->GetFunc)
        {
            return 0;
        }

        // Load all necessary API functions
        #define GET_FUNC(name) *(void **)&name = rec->GetFunc(#name)
        GET_FUNC(ShowConsoleMsg);
        GET_FUNC(CountTracks);
        GET_FUNC(GetTrack);
        GET_FUNC(GetMediaTrackInfo_Value);
        GET_FUNC(SetMediaTrackInfo_Value);
        GET_FUNC(TrackList_AdjustWindows);
        GET_FUNC(Undo_BeginBlock);
        GET_FUNC(Undo_EndBlock);
        GET_FUNC(plugin_register);
        GET_FUNC(CountTrackMediaItems);
        GET_FUNC(GetTrackMediaItem);
        GET_FUNC(GetMediaItemInfo_Value);
        GET_FUNC(TrackFX_SetOpen);
        GET_FUNC(TrackFX_Show);
        GET_FUNC(GetSelectedTrack);
        GET_FUNC(TrackFX_GetCount);
        GET_FUNC(TrackFX_GetEnabled);
        GET_FUNC(TrackFX_GetParamFromIdent);
        GET_FUNC(TrackFX_GetParam);
        GET_FUNC(TrackFX_GetOffline);
        GET_FUNC(TrackFX_GetOpen);
        GET_FUNC(TrackFX_GetFloatingWindow);

        // Register the action
        enz_toggleMutedTracksCmdId = plugin_register("command_id", (void*)"enz_ToggleMutedTracksVisibility");
        if (!enz_toggleMutedTracksCmdId) return 0;

        static gaccel_register_t accelerator;
        accelerator.accel.cmd = enz_toggleMutedTracksCmdId;
        accelerator.desc = "enz_Toggle visibility of muted tracks";
        plugin_register("gaccel", &accelerator);

        // Register the second action
        enz_toggleSelectedTrackFXFloatCmdId = plugin_register("command_id", (void*)"enz_ToggleSelectedTrackFXFloat");
        if (!enz_toggleSelectedTrackFXFloatCmdId) return 0;

        static gaccel_register_t accelerator2;
        accelerator2.accel.cmd = enz_toggleSelectedTrackFXFloatCmdId;
        accelerator2.desc = "enz_Toggle float for selected track FX";
        plugin_register("gaccel", &accelerator2);

        // Register the command hook
        plugin_register("hookcommand", (void*)hook_command);
        
        ShowConsoleMsg("enz_ReaperTools plugin loaded!\n");

        return 1;
    }
    else
    {
        return 0;
    }
}
} // extern "C" 