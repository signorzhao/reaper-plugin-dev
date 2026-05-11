-- @description ENZ UCS Auto Rename Selected Items
-- @author ENZ
-- @version 0.1.0
-- @about
--   Rename selected media items from a Chinese natural-language description
--   using a local ENZ UCS service.

local SCRIPT_TITLE = "ENZ UCS Auto Rename"
local SCRIPT_VERSION = "0.4.0-embedding-preview"
local API_URL = "http://127.0.0.1:8000/api/v1/parse_ucs"
local UI_URL = "http://127.0.0.1:8000/ui"
local UI_STATE_URL = "http://127.0.0.1:8000/api/v1/ui_state"
local REAPER_STATUS_URL = "http://127.0.0.1:8000/api/v1/reaper_status"
local NEXT_TASK_URL = "http://127.0.0.1:8000/api/v1/next_task"
local TASK_COMPLETE_URL = "http://127.0.0.1:8000/api/v1/task_complete"
local SHUTDOWN_URL = "http://127.0.0.1:8000/api/v1/shutdown"
local REQUEST_TIMEOUT_MS = 1000
local CURL_MAX_TIME_SECONDS = "0.6"
local POLL_INTERVAL_SECONDS = 1.0

if not reaper.ImGui_CreateContext then
  reaper.MB("需要先安装 ReaImGui 扩展。", SCRIPT_TITLE, 0)
  return
end

local function imgui_context_flags()
  local flags = 0
  if reaper.ImGui_ConfigFlags_DockingEnable then
    flags = flags | reaper.ImGui_ConfigFlags_DockingEnable()
  end
  if reaper.ImGui_ConfigFlags_NavEnableKeyboard then
    flags = flags | reaper.ImGui_ConfigFlags_NavEnableKeyboard()
  end
  return flags
end

local context_flags = imgui_context_flags()
local ctx = context_flags ~= 0
  and reaper.ImGui_CreateContext(SCRIPT_TITLE, context_flags)
  or reaper.ImGui_CreateContext(SCRIPT_TITLE)
local description = ""
local last_non_empty_description = ""
local status_message = "v" .. SCRIPT_VERSION .. " 保持此窗口打开；用启动器或网页作为主界面。"
local parsed_result = nil
local parsed_description = ""
local selected_candidate = 1
local fx_name_override = ""
local preview_names = {}
local should_close = false
local input_flags = reaper.ImGui_InputTextFlags_EnterReturnsTrue()
local log_path = nil
local json_decode
local rebuild_preview
local last_poll_time = 0
local last_task_id = nil

local function script_dir()
  local source = debug.getinfo(1, "S").source
  local path = source:sub(1, 1) == "@" and source:sub(2) or source
  return path:match("^(.*[\\/])") or ""
end

local function join_path(base, name)
  local separator = package.config:sub(1, 1)
  if base:sub(-1) == "/" or base:sub(-1) == "\\" then
    return base .. name
  end
  return base .. separator .. name
end

local function log_debug(message)
  if not log_path then
    log_path = join_path(script_dir(), "enz_ucs_debug.log")
  end
  local file = io.open(log_path, "a")
  if file then
    file:write(os.date("%Y-%m-%d %H:%M:%S"), " ", tostring(message), "\n")
    file:close()
  end
end

log_debug("script loaded: " .. SCRIPT_VERSION .. " path=" .. tostring(debug.getinfo(1, "S").source))

local function destroy_context()
  if reaper.ImGui_DestroyContext then
    reaper.ImGui_DestroyContext(ctx)
  end
end

local function quote_arg(value)
  return '"' .. tostring(value):gsub('"', '\\"') .. '"'
end

local function curl_executable()
  if package.config:sub(1, 1) == "\\" then
    return "curl.exe"
  end
  return "/usr/bin/curl"
end

local function json_escape(value)
  return tostring(value)
    :gsub("\\", "\\\\")
    :gsub('"', '\\"')
    :gsub("\b", "\\b")
    :gsub("\f", "\\f")
    :gsub("\n", "\\n")
    :gsub("\r", "\\r")
    :gsub("\t", "\\t")
end

local function imgui_input_text(label, value, flags)
  local first, second
  if flags ~= nil then
    first, second = reaper.ImGui_InputText(ctx, label, value, flags)
  else
    first, second = reaper.ImGui_InputText(ctx, label, value)
  end

  if type(first) == "string" then
    return second == true, first
  end
  if type(second) == "string" then
    return first == true, second
  end
  return first == true, value
end

local function read_clipboard_text()
  if reaper.CF_GetClipboard then
    local ok, text = reaper.CF_GetClipboard("")
    if ok and text and text ~= "" then
      return text
    end
  end

  if package.config:sub(1, 1) ~= "\\" then
    local handle = io.popen("/usr/bin/pbpaste 2>/dev/null")
    if handle then
      local text = handle:read("*a") or ""
      handle:close()
      return text
    end
  end

  return ""
end

local function run_curl_get(url)
  local curl = curl_executable()
  local command = table.concat({
    quote_arg(curl),
    "-sS",
    "--max-time",
    CURL_MAX_TIME_SECONDS,
    quote_arg(url),
  }, " ")
  log_debug("curl get command: " .. command)
  return reaper.ExecProcess(command, REQUEST_TIMEOUT_MS)
end

local function run_curl_post_json(url, json_body, temp_name)
  local request_path = join_path(script_dir(), temp_name or "enz_ucs_request.json")
  local file = io.open(request_path, "w")
  if not file then
    return nil, "无法写入临时请求文件。"
  end
  file:write(json_body)
  file:close()

  local curl = curl_executable()
  local command = table.concat({
    quote_arg(curl),
    "-sS",
    "--max-time",
    CURL_MAX_TIME_SECONDS,
    "-H",
    quote_arg("Content-Type: application/json; charset=utf-8"),
    "--data-binary",
    quote_arg("@" .. request_path),
    quote_arg(url),
  }, " ")

  log_debug("curl post command: " .. command)
  local output = reaper.ExecProcess(command, REQUEST_TIMEOUT_MS)
  os.remove(request_path)
  return output, nil
end

local function open_web_ui()
  local command
  if package.config:sub(1, 1) == "\\" then
    command = 'cmd.exe /C start "" ' .. quote_arg(UI_URL)
  else
    command = "/usr/bin/open " .. quote_arg(UI_URL)
  end
  log_debug("open ui command: " .. command)
  reaper.ExecProcess(command, 1000)
  status_message = "已打开网页。保持此窗口打开，网页里点击“在 REAPER 重命名”即可执行。"
end

local function load_web_result()
  local output = run_curl_get(UI_STATE_URL)
  log_debug("ui state output: " .. tostring(output))
  if not output or output == "" then
    status_message = "无法读取网页结果，请确认服务正在运行。"
    return
  end
  local json_start = output:find("{", 1, true)
  if not json_start then
    status_message = "网页结果返回异常。"
    return
  end
  local ok, decoded = pcall(json_decode, output:sub(json_start))
  if not ok or not decoded or decoded.status ~= "success" or not decoded.data then
    status_message = "网页结果无法解析。"
    return
  end
  local state = decoded.data
  if not state.result then
    status_message = "网页还没有结果。请先在网页点击“生成候选”。"
    return
  end
  description = state.description or ""
  last_non_empty_description = description
  parsed_description = description
  parsed_result = state.result
  selected_candidate = tonumber(state.selected_candidate) or 1
  fx_name_override = state.fx_name or parsed_result.fx_name or ""
  rebuild_preview()
  status_message = "已读取网页结果，可手动确认重命名。"
end

local function current_description()
  local trimmed = tostring(description or ""):gsub("^%s+", ""):gsub("%s+$", "")
  if trimmed ~= "" then
    last_non_empty_description = trimmed
    return trimmed
  end
  return last_non_empty_description
end

function json_decode(text)
  local index = 1

  local function skip_ws()
    while index <= #text and text:sub(index, index):match("[ \n\r\t]") do
      index = index + 1
    end
  end

  local function parse_string()
    index = index + 1
    local result = {}
    while index <= #text do
      local char = text:sub(index, index)
      if char == '"' then
        index = index + 1
        return table.concat(result)
      elseif char == "\\" then
        local escaped = text:sub(index + 1, index + 1)
        local map = { ['"'] = '"', ["\\"] = "\\", ["/"] = "/", b = "\b", f = "\f", n = "\n", r = "\r", t = "\t" }
        if escaped == "u" then
          result[#result + 1] = "?"
          index = index + 6
        else
          result[#result + 1] = map[escaped] or escaped
          index = index + 2
        end
      else
        result[#result + 1] = char
        index = index + 1
      end
    end
    error("unterminated JSON string")
  end

  local parse_value

  local function parse_array()
    index = index + 1
    local result = {}
    skip_ws()
    if text:sub(index, index) == "]" then
      index = index + 1
      return result
    end
    while true do
      result[#result + 1] = parse_value()
      skip_ws()
      local char = text:sub(index, index)
      if char == "]" then
        index = index + 1
        return result
      end
      if char ~= "," then
        error("expected comma in JSON array")
      end
      index = index + 1
    end
  end

  local function parse_object()
    index = index + 1
    local result = {}
    skip_ws()
    if text:sub(index, index) == "}" then
      index = index + 1
      return result
    end
    while true do
      skip_ws()
      if text:sub(index, index) ~= '"' then
        error("expected JSON object key")
      end
      local key = parse_string()
      skip_ws()
      if text:sub(index, index) ~= ":" then
        error("expected colon after JSON object key")
      end
      index = index + 1
      result[key] = parse_value()
      skip_ws()
      local char = text:sub(index, index)
      if char == "}" then
        index = index + 1
        return result
      end
      if char ~= "," then
        error("expected comma in JSON object")
      end
      index = index + 1
    end
  end

  function parse_value()
    skip_ws()
    local char = text:sub(index, index)
    if char == '"' then
      return parse_string()
    elseif char == "{" then
      return parse_object()
    elseif char == "[" then
      return parse_array()
    elseif text:sub(index, index + 3) == "true" then
      index = index + 4
      return true
    elseif text:sub(index, index + 4) == "false" then
      index = index + 5
      return false
    elseif text:sub(index, index + 3) == "null" then
      index = index + 4
      return nil
    else
      local start_index = index
      local number_text = text:sub(index):match("^-?%d+%.?%d*[eE]?[+-]?%d*")
      if not number_text or number_text == "" then
        error("invalid JSON value at " .. tostring(index))
      end
      index = start_index + #number_text
      return tonumber(number_text)
    end
  end

  return parse_value()
end

local function selected_items_sorted()
  local items = {}
  local count = reaper.CountSelectedMediaItems(0)
  for i = 0, count - 1 do
    local item = reaper.GetSelectedMediaItem(0, i)
    items[#items + 1] = {
      item = item,
      position = reaper.GetMediaItemInfo_Value(item, "D_POSITION"),
      original_index = i,
    }
  end
  table.sort(items, function(a, b)
    if a.position == b.position then
      return a.original_index < b.original_index
    end
    return a.position < b.position
  end)
  return items
end

local function active_choice()
  if not parsed_result then
    return nil
  end
  local candidates = parsed_result.candidates or {}
  local candidate = candidates[selected_candidate]
  local fx_name = fx_name_override
  if fx_name == "" then
    fx_name = parsed_result.fx_name or ""
  end
  if candidate then
    return {
      ucs_prefix = candidate.ucs_prefix,
      category = candidate.category,
      subcategory = candidate.subcategory,
      fx_name = fx_name,
      confidence = parsed_result.confidence or "low",
      score = candidate.score or parsed_result.score or 0,
      fallback = parsed_result.fallback,
    }
  end
  return parsed_result
end

local function build_name(index)
  local choice = active_choice()
  local base = choice and choice.ucs_prefix or "USERMisc"
  local fx_name = choice and choice.fx_name or ""
  if fx_name ~= "" then
    base = base .. "_" .. fx_name
  end
  return string.format("%s_%02d", base, index)
end

function rebuild_preview()
  preview_names = {}
  local items = selected_items_sorted()
  for i = 1, #items do
    preview_names[i] = build_name(i)
  end
end

local function run_curl_post(desc)
  return run_curl_post_json(API_URL, '{"description":"' .. json_escape(desc) .. '"}', "enz_ucs_parse_request.json")
end

local function test_service()
  local curl = curl_executable()
  local command = table.concat({
    quote_arg(curl),
    "-sS",
    "--max-time",
    CURL_MAX_TIME_SECONDS,
    quote_arg("http://127.0.0.1:8000/health"),
  }, " ")
  log_debug("health command: " .. command)
  local output = reaper.ExecProcess(command, REQUEST_TIMEOUT_MS)
  log_debug("health output: " .. tostring(output))
  if output and output:find('"ok"', 1, true) then
    status_message = "服务连接正常：" .. tostring(output)
  else
    status_message = "服务连接失败，请先运行 ENZ UCS 启动器。"
    reaper.MB(status_message, SCRIPT_TITLE, 0)
  end
end

local function shutdown_service()
  local output = run_curl_post_json(SHUTDOWN_URL, "{}", "enz_ucs_shutdown.json")
  log_debug("shutdown output: " .. tostring(output))
  if output and output:find("success", 1, true) then
    status_message = "已请求关闭后端服务。"
  else
    status_message = "关闭后端失败，服务可能未运行。"
  end
end

local function parse_description()
  local desc = current_description()
  log_debug("parse requested: " .. tostring(desc))
  if desc:gsub("%s+", "") == "" then
    status_message = "请输入描述。"
    reaper.MB(status_message, SCRIPT_TITLE, 0)
    log_debug("parse stopped: empty description")
    return
  end

  local items = selected_items_sorted()
  if #items == 0 then
    status_message = "请先选择一个或多个 media item。"
    reaper.MB(status_message, SCRIPT_TITLE, 0)
    log_debug("parse stopped: no selected items")
    return
  end

  local output, request_error = run_curl_post(desc)
  if request_error then
    status_message = request_error
    reaper.MB(status_message, SCRIPT_TITLE, 0)
    log_debug("parse stopped: " .. request_error)
    return
  end
  log_debug("curl output: " .. tostring(output))

  if not output or output == "" then
    status_message = "本地 UCS 翻译服务未运行，请检查后台。"
    reaper.MB(status_message, SCRIPT_TITLE, 0)
    log_debug("parse stopped: empty curl output")
    return
  end

  local json_start = output:find("{", 1, true)
  if not json_start then
    status_message = "本地 UCS 翻译服务未运行，请检查后台。"
    reaper.MB(status_message .. "\n\ncurl 输出：\n" .. tostring(output), SCRIPT_TITLE, 0)
    log_debug("parse stopped: no JSON object in curl output")
    return
  end

  local ok, decoded = pcall(json_decode, output:sub(json_start))
  if not ok or not decoded or decoded.status ~= "success" or not decoded.data then
    status_message = "UCS 服务返回内容无法解析。"
    reaper.MB(status_message .. "\n\ncurl 输出：\n" .. tostring(output), SCRIPT_TITLE, 0)
    log_debug("parse stopped: JSON decode failed")
    return
  end

  parsed_result = decoded.data
  parsed_description = desc
  selected_candidate = 1
  fx_name_override = parsed_result.fx_name or ""
  if not parsed_result.candidates or #parsed_result.candidates == 0 then
    parsed_result.candidates = {
      {
        ucs_prefix = parsed_result.ucs_prefix or "USERMisc",
        category = parsed_result.category or "USER",
        subcategory = parsed_result.subcategory or "MISC",
        score = parsed_result.score or 0,
      },
    }
  end
  rebuild_preview()
  status_message = "检查候选、编辑 FXName，然后确认重命名。"
  log_debug("parse ok: " .. tostring(parsed_result.ucs_prefix))
end

local function rename_items()
  log_debug("rename requested")
  local items = selected_items_sorted()
  if #items == 0 then
    status_message = "请先选择一个或多个 media item。"
    log_debug("rename stopped: no selected items")
    return false, status_message
  end
  if not parsed_result then
    status_message = "还没有可执行的 UCS 结果。请先在网页生成候选。"
    log_debug("rename stopped: no parsed result")
    return false, status_message
  end

  reaper.Undo_BeginBlock()
  reaper.PreventUIRefresh(1)
  for i = 1, #items do
    local take = reaper.GetActiveTake(items[i].item)
    if take then
      reaper.GetSetMediaItemTakeInfo_String(take, "P_NAME", build_name(i), true)
    end
  end
  reaper.PreventUIRefresh(-1)
  reaper.UpdateArrange()
  reaper.Undo_EndBlock("ENZ UCS auto rename selected items", -1)
  log_debug("rename ok: " .. tostring(#items) .. " items")
  status_message = "已重命名 " .. tostring(#items) .. " 个 item。窗口保持打开，可继续选择下一批。"
  return true, status_message
end

local function ensure_candidates()
  if parsed_result and (not parsed_result.candidates or #parsed_result.candidates == 0) then
    parsed_result.candidates = {
      {
        ucs_prefix = parsed_result.ucs_prefix or "USERMisc",
        category = parsed_result.category or "USER",
        subcategory = parsed_result.subcategory or "MISC",
        score = parsed_result.score or 0,
      },
    }
  end
end

local function task_complete(task_id, ok, message)
  local body = table.concat({
    '{"id":', tostring(task_id or 0),
    ',"ok":', ok and "true" or "false",
    ',"message":"', json_escape(message or ""), '"}'
  })
  local output = run_curl_post_json(TASK_COMPLETE_URL, body, "enz_ucs_task_complete.json")
  log_debug("task complete output: " .. tostring(output))
end

local function run_task(task)
  if not task or not task.id then
    return
  end
  if last_task_id == task.id then
    return
  end
  last_task_id = task.id
  description = task.description or ""
  last_non_empty_description = description
  parsed_description = description
  parsed_result = task.result
  selected_candidate = tonumber(task.selected_candidate) or 1
  fx_name_override = task.fx_name or (parsed_result and parsed_result.fx_name) or ""
  ensure_candidates()
  rebuild_preview()

  local ok, message = rename_items()
  task_complete(task.id, ok, message)
end

local function post_reaper_status()
  local body = table.concat({
    '{"selected_item_count":', tostring(reaper.CountSelectedMediaItems(0)),
    ',"message":"', json_escape(status_message), '"}'
  })
  local output = run_curl_post_json(REAPER_STATUS_URL, body, "enz_ucs_reaper_status.json")
  return output and output:find("{", 1, true) ~= nil
end

local function poll_backend()
  local now = reaper.time_precise()
  if now - last_poll_time < POLL_INTERVAL_SECONDS then
    return
  end
  last_poll_time = now

  if not post_reaper_status() then
    return
  end
  local output = run_curl_get(NEXT_TASK_URL)
  if not output or output == "" then
    return
  end
  local json_start = output:find("{", 1, true)
  if not json_start then
    return
  end
  local ok, decoded = pcall(json_decode, output:sub(json_start))
  if ok and decoded and decoded.status == "success" and decoded.data then
    run_task(decoded.data)
  end
end

local function draw_candidates()
  if not parsed_result then
    return
  end
  reaper.ImGui_Separator(ctx)
  reaper.ImGui_Text(ctx, "UCS 候选")
  local candidates = parsed_result.candidates or {}
  for i = 1, math.min(#candidates, 3) do
    local candidate = candidates[i]
    local label = string.format(
      "%s  %s/%s  %.1f",
      candidate.ucs_prefix or "",
      candidate.zh_category or candidate.category or "",
      candidate.zh_subcategory or candidate.subcategory or "",
      candidate.score or 0
    )
    if reaper.ImGui_RadioButton(ctx, label .. "##candidate" .. i, selected_candidate == i) then
      selected_candidate = i
      rebuild_preview()
    end
  end
  local changed
  changed, fx_name_override = imgui_input_text("FXName##fx_name", fx_name_override)
  if changed then
    rebuild_preview()
  end
  reaper.ImGui_Text(ctx, "置信度: " .. (parsed_result.confidence or "low"))
end

local function draw_preview()
  if #preview_names == 0 then
    return
  end
  reaper.ImGui_Separator(ctx)
  reaper.ImGui_Text(ctx, "预览")
  for i = 1, math.min(#preview_names, 8) do
    reaper.ImGui_Text(ctx, preview_names[i])
  end
  if #preview_names > 8 then
    reaper.ImGui_Text(ctx, string.format("... 还有 %d 个", #preview_names - 8))
  end
end

local function loop()
  poll_backend()

  if should_close then
    destroy_context()
    return
  end

  reaper.ImGui_SetNextWindowSize(ctx, 720, 520, reaper.ImGui_Cond_FirstUseEver())
  local visible, open = reaper.ImGui_Begin(ctx, SCRIPT_TITLE, true)
  if visible then
    reaper.ImGui_TextWrapped(ctx, status_message)
    local item_count = reaper.CountSelectedMediaItems(0)
    reaper.ImGui_Text(ctx, "选中 Item: " .. tostring(item_count))
    reaper.ImGui_TextWrapped(ctx, "当前描述: " .. (current_description() ~= "" and current_description() or "(请在网页输入)"))

    if reaper.ImGui_Button(ctx, "打开网页") then
      open_web_ui()
    end
    reaper.ImGui_SameLine(ctx)
    if reaper.ImGui_Button(ctx, "读取网页结果") then
      load_web_result()
    end
    reaper.ImGui_SameLine(ctx)
    if reaper.ImGui_Button(ctx, "手动确认重命名") then
      if parsed_result then
        rename_items()
      else
        status_message = "请先生成预览。"
      end
    end
    reaper.ImGui_SameLine(ctx)
    if reaper.ImGui_Button(ctx, "测试服务") then
      test_service()
    end
    reaper.ImGui_SameLine(ctx)
    if reaper.ImGui_Button(ctx, "关闭后端") then
      shutdown_service()
    end
    reaper.ImGui_SameLine(ctx)
    if reaper.ImGui_Button(ctx, "清空") then
      description = ""
      last_non_empty_description = ""
      parsed_result = nil
      parsed_description = ""
      preview_names = {}
      fx_name_override = ""
      status_message = "已清空。"
    end
    reaper.ImGui_SameLine(ctx)
    if reaper.ImGui_Button(ctx, "关闭") then
      should_close = true
    end

    draw_candidates()
    draw_preview()
    reaper.ImGui_End(ctx)
  end

  if open then
    reaper.defer(loop)
  else
    destroy_context()
  end
end

reaper.defer(loop)
