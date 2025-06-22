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

// Global variable for our command ID
static int g_toggleMutedTracksCmdId = 0;

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

    Undo_EndBlock("Toggle Muted Tracks Visibility", -1);
    TrackList_AdjustWindows(true); // Update both TCP and MCP
}

// Hook function that REAPER calls for our action
static bool hook_command(int commandId, int flag)
{
    if (commandId == g_toggleMutedTracksCmdId)
    {
        ToggleMutedTracksVisibility();
        return true; // Command was handled
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

        // Register the action
        g_toggleMutedTracksCmdId = plugin_register("command_id", (void*)"ToggleMutedTracksVisibility");
        if (!g_toggleMutedTracksCmdId) return 0;

        static gaccel_register_t accelerator;
        accelerator.accel.cmd = g_toggleMutedTracksCmdId;
        accelerator.desc = "IAN: Toggle visibility of muted tracks";
        plugin_register("gaccel", &accelerator);

        // Register the command hook
        plugin_register("hookcommand", (void*)hook_command);
        
        ShowConsoleMsg("IAN's Muted Track Toggler plugin loaded!\n");

        return 1;
    }
    else
    {
        return 0;
    }
}
} // extern "C" 