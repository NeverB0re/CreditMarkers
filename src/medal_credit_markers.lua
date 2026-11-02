-- HD2-Addon: mods/codex/medal_credit_markers
-- HD2-Keep-On-Crash: yes
-- Medal & Super Credit Markers: medals and super credits lying about the map, marked from far away with the game's
-- own currency icons and their distance. Reads and draws only; it changes no game state.
--
-- Stability comes first, so it asks the engine as little as it can, and only through Chef Shared Loader's guards:
--   * no helldiver is read: distance is across the ground from the camera (so it works from a hellpod, too);
--   * no node is asked for (Unit.has_node on a vehicle is what a player's crash named in the sister mod);
--   * a resource is looked up only when Application.can_get says it is loaded, one a tick, each once a second;
--   * known units are read 4 times a second, and only in a mission of a settled world;
--   * the markers are worked out 4 times a second; only drawing them happens every frame.

local MOD_KEY = 'MedalCreditMarkers'
if rawget(_G, MOD_KEY) then return rawget(_G, MOD_KEY) end

local CHEF = ...
if type(CHEF) ~= 'table' then CHEF = nil end
local CHEF_NEEDS = {'camera', 'call_kind', 'unit_alive', 'unit_position', 'in_mission', 'world', 'world_id',
                    'screen', 'color', 'rect', 'bitmap', 'text', 'text_width', 'log'}

local VERSION = '1.0.0'
local TITLE = 'Medal & Super Credit Markers'
local M = {version = VERSION, status = 'starting', dots = {}}
rawset(_G, MOD_KEY, M)

-- ------------------------------------------------------------------ settings --
local LOOK = {
    show_medal = true,
    show_credit = true,
    range = 2000,         -- metres across the ground from the camera: a whole map, end to end
    distance = true,      -- the distance above a marker
}
local ROWS = {   -- id, kind, label, description, and a slider's most and step
    {'show_medal', 'toggle', 'Show medals', 'Medals lying about the map.'},
    {'show_credit', 'toggle', 'Show super credits', 'Super credits lying about the map.'},
    {'range', 'slider', 'Distance (m)', 'Marked within this many metres of the camera, across the ground.', 2000, 50},
    {'distance', 'toggle', 'Show distance above markers', 'How far away each marked item is.'},
}

-- ------------------------------------------------------------------- targets --
-- From packages/generated/exploration_rewards (filediver). The medal's id has no name in the game's hash list: it is
-- a cache box with the medal's skull and octagon on it, and played, those are the markers on the medals.
local TARGETS = {
    {draw = 'credit', name = 'content/env_super_earth/economy_items/super_credit/super_credit_stack'},
    {draw = 'medal', hex = '773c4184e4bad0df'},
}
local ICON_TEX = "@ICONS@"
local ICON_RGB = {medal = {255, 221, 31}, credit = {144, 213, 246}}   -- the distance, in its icon's colour
local ICON_SIZE = 30          -- pixels along the longer side, at full size on a 1080-line screen
local DOT_HEIGHT = 0.8        -- metres above the unit's root
local SMALLEST = 0.7          -- size from SMALLEST_AT_M on; full size up to FULL_SIZE_M
local FULL_SIZE_M, SMALLEST_AT_M = 25, 500
local MAX_MARKERS = 30        -- the nearest only
local LAYER = 900             -- Chef Shared Loader's layer (under the game's HUD and menus)
local DISTANCE_PX = 1.6       -- the loader's text size at 1080 pixels of screen
local BOLD = {{0, 0}, {1, 0}, {0, 1}, {1, 1}}   -- the distance drawn at each: the loader's text has one thin weight
local UI_W, UI_H = 1920, 1080 -- the game scales its HUD by the smaller of width / 1920 and height / 1080
local VERTICAL_FOV = 50       -- degrees, when the camera doesn't give it

local STARTUP_GRACE_S = 10    -- wait after start before touching the world
local WORLD_SETTLE_S = 8      -- wait after a world appears before looking anything up in it
local LOOKUP_EVERY_S = 1      -- each resource looked up this often
local READ_EVERY_S = 0.25     -- known units read, and the markers worked out, this often
local BOX_EVERY_S = 1         -- a unit's visible geometry asked this often ...
local BOX_PER_READ = 2        -- ... and at most this many units at a read
local STATUS_EVERY_S = 60     -- a summary line in the log this often, when it changed
local AVATAR_HEX = '4d1c334d294dfa97'   -- id self-test: the helldiver is loaded, a made-up id is not
local BOGUS_HEX = '0123456789abcdef'

-- ----------------------------------------------------------------------- log --
-- The loader's own log file for this mod, MedalCreditMarkers.log in its folder: kept across launches, so a launch
-- that crashed stays readable, and capped by the loader. (A mod may not read its old logs itself: Chef 1.4 refuses.)
if CHEF and type(CHEF.own_log) == 'function' then pcall(CHEF.own_log, 'MedalCreditMarkers') end

local function log(message)
    if CHEF and type(CHEF.log) == 'function' then pcall(CHEF.log, '%s', tostring(message)) end
end

-- ------------------------------------------------------------- engine access --
local sr = rawget(_G, 'stingray')
local can_get = sr and sr.Application and type(sr.Application.can_get) == 'function' and sr.Application.can_get

local function check_api()
    if CHEF == nil then return 'no Chef Shared Loader' end
    if type(sr) ~= 'table' then return 'no engine' end
    local missing = {}
    for _, name in ipairs(CHEF_NEEDS) do
        if type(CHEF[name]) ~= 'function' then missing[#missing + 1] = name end
    end
    if #missing > 0 then return 'Chef Shared Loader without ' .. table.concat(missing, ', ') .. ' (too old?)' end
end

local function as_list(value)
    if type(value) ~= 'table' then return {} end
    if value[1] ~= nil or next(value) == nil then return value end
    local out = {}
    for _, item in pairs(value) do out[#out + 1] = item end
    return out
end

-- Script temp memory (the engine's vectors) isn't reset for mods: put back every frame.
local function temp_begin()
    if sr.Script and type(sr.Script.temp_byte_count) == 'function' then
        local ok, saved = pcall(sr.Script.temp_byte_count)
        if ok then return saved end
    end
end
local function temp_end(saved)
    if saved ~= nil then pcall(sr.Script.set_temp_byte_count, saved) end
end

-- Ids: can_get understands one form on this game, found by a self-test. Without one, the id-only targets stay off.
local id_form      -- 'IdString64' | 'text' | false | nil (not tested yet)

local function id_key(hex, form)
    if form == 'IdString64' then
        if not (sr.IdString64 and type(sr.IdString64.from_hex) == 'function') then return nil end
        local ok, value = pcall(sr.IdString64.from_hex, hex)
        if ok then return value end
    elseif form == 'text' then
        return '#ID[' .. hex .. ']'
    end
end

local function is_loaded(key)
    if not can_get or key == nil then return nil end
    local ok, yes = pcall(can_get, 'unit', key)
    if ok then return yes == true end
end

local function detect_id_form()
    if id_form ~= nil or not can_get then return end
    for _, form in ipairs({'IdString64', 'text'}) do
        if is_loaded(id_key(AVATAR_HEX, form)) == true and is_loaded(id_key(BOGUS_HEX, form)) == false then
            id_form = form
            log('ids: form ' .. form .. ' works')
            return
        end
    end
    id_form = false
    log('ids: no form passed the self-test - the medal stays off')
end

-- The key to ask can_get with and the one to look units up with, or nil to skip.
local function keys_of(t)
    if t.name then return t.name, t.name end
    if not id_form then return nil end
    return id_key(t.hex, id_form), id_key(t.hex, 'IdString64')
end

-- Where a unit is, as plain numbers, or nil.
local function position_of(unit)
    local oka, alive = pcall(CHEF.unit_alive, unit)
    if not oka or alive ~= true then return nil end
    local ok, x, y, z = pcall(CHEF.unit_position, unit)
    if not ok or type(x) ~= 'number' or type(y) ~= 'number' or type(z) ~= 'number' then return nil end
    if x ~= x or y ~= y or z ~= z or math.abs(x) > 1e7 or math.abs(y) > 1e7 or math.abs(z) > 1e7 then return nil end
    return x, y, z
end

-- Does this unit show nothing any more? True: hidden, false: shown, nil: can't be told (a refused answer changes
-- nothing: it may be coming back, or just not ready).
local function geometry_gone(item, label)
    local ok, _, extents = pcall(CHEF.call_kind, 'Unit.box', label, item.unit, true)
    if not ok or extents == nil then return nil end
    local got, x, y, z = pcall(function() return sr.Vector3.x(extents), sr.Vector3.y(extents), sr.Vector3.z(extents) end)
    if not got or type(x) ~= 'number' then return nil end
    return x == 0 and y == 0 and z == 0
end

-- -------------------------------------------------------------- what is there --
local items = {}        -- per target index: list of {unit, x, y, z, seen_shown, hidden, box_at}
local counts = {}       -- per target index: how many at its last look, for the log
local cursor = 1
local next_lookup, next_read, next_status = 0, 0, 0
local last_status
local failures = 0

local function forget_units()
    items, counts, cursor, next_lookup, next_read = {}, {}, 1, 0, 0
    M.dots = {}
end

-- One resource: its members now, keeping what is known of the ones still there.
local function look_up(i, world)
    local t = TARGETS[i]
    local ask, lookup = keys_of(t)
    if is_loaded(ask) ~= true or lookup == nil then
        items[i], counts[i] = nil, 0
        return
    end
    local ok, value, why = pcall(CHEF.call_kind, 'World.units_by_resource', t.name or t.hex, world, lookup)
    if not ok or value == nil then
        failures = failures + 1
        if failures <= 5 then log('lookup failed for ' .. (t.name or t.hex) .. ': ' .. tostring(ok and why or value)) end
        return   -- keep what is known: a refused look isn't an empty one
    end
    local by = {}
    for _, item in ipairs(items[i] or {}) do by[item.unit] = item end
    local now = {}
    for _, unit in ipairs(as_list(value)) do now[#now + 1] = by[unit] or {unit = unit} end
    items[i], counts[i] = now, #now
end

-- Reads known units; asks a few of them whether they still show anything (a picked-up item may stay, hidden).
local function read_units(t_now)
    local asked = 0
    for i = 1, #TARGETS do
        local list, t = items[i], TARGETS[i]
        for k = #(list or {}), 1, -1 do
            local item = list[k]
            local x, y, z = position_of(item.unit)
            if not x then
                table.remove(list, k)
                if item.seen_shown and not item.hidden then log(t.draw .. ': one is gone (the unit went)') end
            else
                item[1], item[2], item[3] = x, y, z
                if asked < BOX_PER_READ and t_now >= (item.box_at or 0) then
                    asked = asked + 1
                    item.box_at = t_now + BOX_EVERY_S
                    local gone = geometry_gone(item, t.name or t.hex)
                    if gone == false then
                        if item.hidden then log(t.draw .. ': one shows again') end
                        item.seen_shown, item.hidden = true, false
                    elseif gone == true and item.seen_shown and not item.hidden then
                        item.hidden = true
                        log(t.draw .. ': one shows nothing any more (taken)')
                    end
                end
            end
        end
    end
end

-- The markers now, nearest first: {x, y, z, distance, icon, its size at this distance, its distance as text}.
local function collect(cam)
    local dots = {}
    local cx, cy = cam.translation[1], cam.translation[2]
    for i = 1, #TARGETS do
        local icon = TARGETS[i].draw
        if LOOK['show_' .. icon] ~= false then
            for _, item in ipairs(items[i] or {}) do
                if item[1] and not item.hidden then
                    local dx, dy = item[1] - cx, item[2] - cy
                    local d = math.sqrt(dx * dx + dy * dy)
                    if d <= LOOK.range then
                        local far = math.max(0, math.min(1, (d - FULL_SIZE_M) / (SMALLEST_AT_M - FULL_SIZE_M)))
                        dots[#dots + 1] = {item[1], item[2], item[3] + DOT_HEIGHT, d, icon, 1 - (1 - SMALLEST) * far,
                                           string.format('%dm', math.floor(d + 0.5))}
                    end
                end
            end
        end
    end
    table.sort(dots, function(a, b) return a[4] < b[4] end)
    for k = #dots, MAX_MARKERS + 1, -1 do dots[k] = nil end
    return dots
end

-- ----------------------------------------------------------------------- draw --
-- The game's own camera: where it is, where it looks, and its real field of view. Level: no roll.
local function camera_of()
    local ok, d = pcall(CHEF.camera)
    if not ok or type(d) ~= 'table' or type(d.x) ~= 'number' or type(d.fx) ~= 'number' then return nil end
    local fx, fy, fz = d.fx, d.fy, d.fz
    local level = math.sqrt(fx * fx + fy * fy)
    if level < 1e-6 then return nil end
    local rx, ry = fy / level, -fx / level
    local cam = {translation = {d.x, d.y, d.z}, forward = {fx, fy, fz}, right = {rx, ry, 0},
                 up = {ry * fz, -rx * fz, rx * fy - ry * fx}}
    if type(d.fov) == 'number' and d.fov > 0 then cam.fov = d.fov < 3.2 and math.deg(d.fov) or d.fov end
    return cam
end

local notes = {}   -- what was logged once

local function draw(dots, cam)
    if #dots == 0 then return end
    local oks, cw, ch = pcall(CHEF.screen)
    if not oks or type(cw) ~= 'number' or type(ch) ~= 'number' or cw <= 0 or ch <= 0 then return end
    local width, height = cw, ch
    if sr.Gui and type(sr.Gui.resolution) == 'function' then
        local okr, rw, rh = pcall(sr.Gui.resolution)
        if okr and type(rw) == 'number' and type(rh) == 'number' and rw >= 1 and rh >= 1 then width, height = rw, rh end
    end
    local kx, ky = cw / width, ch / height
    local f = (height / 2) / math.tan(math.rad(cam.fov or VERTICAL_FOV) / 2)
    local ui = math.min(width / UI_W, height / UI_H)
    local tx, ty, tz = cam.translation[1], cam.translation[2], cam.translation[3]
    local fw, ri, up = cam.forward, cam.right, cam.up
    local white = CHEF.color(255, 255, 255, 255)
    local inks = {}    -- a colour lasts its frame: made once a frame, per icon
    for _, d in ipairs(dots) do
        local px, py, pz = d[1] - tx, d[2] - ty, d[3] - tz
        local depth = px * fw[1] + py * fw[2] + pz * fw[3]
        if depth >= 0.5 then
            local sx = width / 2 + (px * ri[1] + py * ri[2] + pz * ri[3]) / depth * f
            local sy = height / 2 + (px * up[1] + py * up[2] + pz * up[3]) / depth * f
            if sx >= 0 and sx <= width and sy >= 0 and sy <= height then
                sx, sy = math.floor(sx + 0.5), math.floor(sy + 0.5)
                local long = ICON_SIZE * ui * d[6]
                local sizes = ICON_TEX[d[5]]
                local t = sizes[#sizes]
                for _, s in ipairs(sizes) do
                    if s[1] >= long * kx then t = s; break end
                end
                local w, h = t[3] * long / t[1], t[4] * long / t[1]
                local ink = inks[d[5]]
                if ink == nil then
                    local rgb = ICON_RGB[d[5]]
                    ink = CHEF.color(rgb[1], rgb[2], rgb[3], 255)
                    inks[d[5]] = ink
                end
                local okd, drawn = pcall(CHEF.bitmap, t[2], math.floor((sx - w / 2) * kx + 0.5),
                    math.floor((sy - h / 2) * ky + 0.5), w * kx, h * ky, white, LAYER)
                if not (okd and drawn) then
                    if not notes.texture then
                        notes.texture = true
                        log('icons: the texture ' .. tostring(t[2]) .. ' could not be drawn (' .. tostring(drawn) .. ') - squares instead')
                    end
                    CHEF.rect((sx - w / 2) * kx, (sy - h / 2) * ky, w * kx, h * ky, ink, LAYER)
                end
                if LOOK.distance then
                    local size = math.max(1, ch / 1080 * DISTANCE_PX)
                    local x = sx * kx - CHEF.text_width(d[7], size) / 2
                    local y = (sy + h / 2 + 3) * ky
                    for _, o in ipairs(BOLD) do CHEF.text(x + o[1], y + o[2], d[7], size, ink) end
                end
            end
        end
    end
end

-- A menu is open (Esc, the map...) while the mouse cursor shows: nothing is drawn then.
local function menu_open()
    if notes.no_cursor then return false end
    local fn = sr.Window and sr.Window.show_cursor
    local ok, value
    if type(fn) == 'function' then ok, value = pcall(fn) end
    if not ok then
        notes.no_cursor = true
        log('menus: Window.show_cursor can\'t be asked - markers stay over menus')
        return false
    end
    return value == true
end

-- ----------------------------------------------------------------------- tick --
local started_at, last_world_id, world_seen_at

local function tick()
    local now = os.clock()
    if now - started_at < STARTUP_GRACE_S then return end
    -- A coherent snapshot of the world, or wait: never around the loader's guard.
    local ok1, id = pcall(CHEF.world_id)
    local okw, world = pcall(CHEF.world)
    local ok2, after = pcall(CHEF.world_id)
    if not (ok1 and okw and ok2) or world == nil or id ~= after then
        if last_world_id ~= nil then
            last_world_id = nil
            forget_units()
        end
        return
    end
    if id ~= last_world_id then
        last_world_id, world_seen_at = id, now
        forget_units()
    end
    if now - world_seen_at < WORLD_SETTLE_S then return end
    local okm, in_mission = pcall(CHEF.in_mission)
    if not okm or not in_mission then
        if next(items) ~= nil then forget_units() end
        return
    end
    local saved = temp_begin()
    local ok, problem = pcall(function()
        detect_id_form()
        if now >= next_lookup then   -- one resource a tick, each once in LOOKUP_EVERY_S
            look_up(cursor, world)
            cursor = cursor % #TARGETS + 1
            next_lookup = now + LOOKUP_EVERY_S / #TARGETS
        end
        local cam = camera_of()
        if now >= next_read then
            next_read = now + READ_EVERY_S
            read_units(now)
            if cam then M.dots = collect(cam) end
        end
        if cam and not menu_open() then draw(M.dots, cam) end
    end)
    temp_end(saved)
    if not ok then
        M.tick_errors = (M.tick_errors or 0) + 1
        if M.tick_errors <= 5 then log('tick failed: ' .. tostring(problem)) end
    end
    if now >= next_status then
        next_status = now + STATUS_EVERY_S
        local status = 'status: markers=' .. #M.dots
        for i, t in ipairs(TARGETS) do status = status .. ' ' .. t.draw .. '=' .. (counts[i] or 0) end
        if status ~= last_status then
            last_status = status
            log(status)
        end
    end
end

-- ------------------------------------------------------------------- settings --
-- Through the loader's Mod Options Menu stand-in: shown in its F9 menu, applied at once. Keys of their own.
local function register_settings()
    local host = rawget(_G, 'ModOptionsMenu')
    if type(host) ~= 'table' or type(host.register_option) ~= 'function' then
        log('settings: no options menu; the defaults')
        return
    end
    for _, row in ipairs(ROWS) do
        local id, field = 'medal_credit_markers.' .. row[1], row[1]
        local spec, set
        if row[2] == 'toggle' then
            spec = {type = 'toggle', default = LOOK[field]}
            set = function(value) if type(value) == 'boolean' then LOOK[field] = value end end
        else
            local most = row[5]
            spec = {type = 'slider', default = LOOK[field], min = 0, max = most, step = row[6]}
            set = function(value)
                value = tonumber(value)
                if value == nil or value ~= value then return end
                LOOK[field] = math.max(0, math.min(most, math.floor(value + 0.5)))
            end
        end
        spec.mod, spec.label, spec.description = TITLE, row[3], row[4]
        local ok, registered, why = pcall(host.register_option, id, spec)
        if not ok or registered ~= true then log('settings: register failed: ' .. tostring(ok and why or registered)) end
        if type(host.get) == 'function' then
            local okg, value = pcall(host.get, id)
            if okg then set(value) end
        end
        if type(host.on_change) == 'function' then pcall(host.on_change, id, set) end
    end
end

-- -------------------------------------------------------------------- install --
local function install()
    log(TITLE .. ' ' .. VERSION .. ' loading')
    local missing = check_api()
    if missing then
        log('FATAL: ' .. missing)
        M.status = missing
        return M
    end
    if type(CHEF.title) == 'function' then pcall(CHEF.title, TITLE) end
    if not can_get then log('Application.can_get is missing: nothing is looked up') end
    register_settings()
    started_at = os.clock()
    local previous = rawget(_G, 'update')
    if type(previous) ~= 'function' then
        log('FATAL: no global update function to hook')
        M.status = 'no update hook'
        return M
    end
    -- after the game's own update: the camera has moved for this frame
    local function after(...)
        if not M.disabled then
            local ok, problem = pcall(tick)
            if not ok then
                M.disabled = true
                log('disabled after error: ' .. tostring(problem))
            end
        end
        return ...
    end
    rawset(_G, 'update', function(...) return after(previous(...)) end)
    M.status = 'running'
    log('running: range=' .. LOOK.range)
    return M
end

return install()
