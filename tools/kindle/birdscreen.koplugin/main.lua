--[[--
Bird screen: starred birds from scott-ouellette.com as the sleep screen.

The site lists the latest POOL starred birds at /birds/kindle.json and renders
each for this panel (1072x1448, 16 grays) at /birds/kindle.png?frame=<key>.
This keeps a folder holding exactly that pool, one file per bird named by its
key, so a bird is downloaded once and dropped when it falls out of the pool.
KOReader's "random image" sleep screen points at the folder, so every sleep
shows a different bird without needing Wi-Fi.

Amazon's own sleep screen (the ScreenSavers hack) is updated by the Bird
screen KUAL extension's sync script, which this runs after each sync.

It syncs when Wi-Fi connects (or on wake while online), at most every few
hours, and from Tools > Bird screen > Refresh now. A failed download keeps
what was there.

Bird mode (Tools > Bird mode, also a gesture action) shows the same birds
full screen for a small child: a tap or swipe anywhere shows another bird,
and every other touch is swallowed, so nothing else can be opened. Only a
long press along the top edge closes it.
--]]--

local DataStorage = require("datastorage")
local Device = require("device")
local Dispatcher = require("dispatcher")
local Geom = require("ui/geometry")
local GestureRange = require("ui/gesturerange")
local ImageWidget = require("ui/widget/imagewidget")
local InfoMessage = require("ui/widget/infomessage")
local InputContainer = require("ui/widget/container/inputcontainer")
local NetworkMgr = require("ui/network/manager")
local UIManager = require("ui/uimanager")
local WidgetContainer = require("ui/widget/container/widgetcontainer")
local lfs = require("libs/libkoreader-lfs")
local logger = require("logger")
local _ = require("gettext")

local SITE = "https://www.scott-ouellette.com/birds/"
local DIR = DataStorage:getDataDir() .. "/birdscreen"
local SYNC_SH = "/mnt/us/extensions/birdscreen/bin/sync.sh" -- also updates Amazon's sleep screen
local MIN_INTERVAL = 3 * 3600 -- seconds between automatic syncs
local EXIT_STRIP = 0.08 -- Bird mode closes on a long press in this top share of the screen

local Screen = Device.screen

-- Bird mode deals birds like cards: every bird once before any repeats, with
-- the same species kept apart (the pool can hold many Red-tailed Hawks). The
-- deck lasts the whole KOReader session, so reopening Bird mode carries on.
local SPREAD = 6 -- keep a species out of this many birds after it, if possible
local Deck = { order = {}, pos = 1, recent = {}, size = 0 }

-- {key: species} from the pool list (the plugin's own copy, or the KUAL sync's).
local function loadSpecies()
    for _i, path in ipairs{ DIR .. "/.pool.json", "/mnt/us/extensions/birdscreen/pool.json" } do
        local fh = io.open(path, "r")
        if fh then
            local ok, data = pcall(require("json").decode, fh:read("*a"))
            fh:close()
            if ok and type(data) == "table" and type(data.species) == "table" then return data.species end
        end
    end
    return {}
end

function Deck:deal(files)
    local species = loadSpecies()
    local function kind(path)
        local key = path:match("([^/]+)%.png$")
        local s = species[key]
        return (s and s ~= "") and s or key -- unknown species: its own kind
    end
    local pile, left, kinds = {}, {}, 0
    for i, f in ipairs(files) do
        pile[i] = f
        local k = kind(f)
        if not left[k] then kinds = kinds + 1 end
        left[k] = (left[k] or 0) + 1
    end
    for i = #pile, 2, -1 do -- shuffle
        local j = math.random(i)
        pile[i], pile[j] = pile[j], pile[i]
    end
    local spread = math.min(SPREAD, kinds - 1)
    local order = {}
    while #pile > 0 do
        -- Of the birds whose species was not just shown, take the commonest
        -- species first so it does not bunch up at the end (ties: shuffled).
        local best
        for i, f in ipairs(pile) do
            local k, clash = kind(f), false
            for _j, r in ipairs(self.recent) do
                if r == k then clash = true; break end
            end
            if not clash and (not best or left[k] > left[kind(pile[best])]) then best = i end
        end
        local f = table.remove(pile, best or 1)
        local k = kind(f)
        left[k] = left[k] - 1
        table.insert(order, f)
        table.insert(self.recent, k)
        while #self.recent > spread do table.remove(self.recent, 1) end
    end
    self.order, self.pos, self.size = order, 1, #files
end

-- The next bird's path, dealing a fresh deck when this one runs out or the
-- pool changed (a sync added or dropped birds).
function Deck:next(files)
    for _i = 1, 2 do
        if self.pos > #self.order or self.size ~= #files then self:deal(files) end
        while self.pos <= #self.order do
            local f = self.order[self.pos]
            self.pos = self.pos + 1
            if lfs.attributes(f, "mode") == "file" then return f end
        end
    end
    return files[1]
end

-- Full-screen bird viewer for a toddler. Modal, and it claims every gesture,
-- so taps never reach the reader or menus underneath.
local BirdMode = InputContainer:extend{
    name = "BirdMode",
    modal = true,
    covers_fullscreen = true,
    stop_events_propagation = true,
    files = nil, -- list of PNG paths
}

function BirdMode:init()
    local w, h = Screen:getWidth(), Screen:getHeight()
    self.dimen = Geom:new{ x = 0, y = 0, w = w, h = h }
    local range = self.dimen
    self.ges_events = {
        Tap = { GestureRange:new{ ges = "tap", range = range } },
        Swipe = { GestureRange:new{ ges = "swipe", range = range } },
        Hold = { GestureRange:new{ ges = "hold", range = range } },
        -- Swallowed, so they cannot reach anything underneath.
        HoldRelease = { GestureRange:new{ ges = "hold_release", range = range } },
        Pan = { GestureRange:new{ ges = "pan", range = range } },
        PanRelease = { GestureRange:new{ ges = "pan_release", range = range } },
        DoubleTap = { GestureRange:new{ ges = "double_tap", range = range } },
        TwoFingerTap = { GestureRange:new{ ges = "two_finger_tap", range = range } },
        Pinch = { GestureRange:new{ ges = "pinch", range = range } },
        Spread = { GestureRange:new{ ges = "spread", range = range } },
        MultiSwipe = { GestureRange:new{ ges = "multiswipe", range = range } },
    }
    self:showBird()
end

function BirdMode:showBird()
    local pick = Deck:next(self.files)
    if self[1] then self[1]:free() end
    self[1] = ImageWidget:new{
        file = pick,
        file_do_cache = false,
        width = self.dimen.w,
        height = self.dimen.h,
        scale_factor = 0, -- fit the screen, keeping the shape
    }
end

function BirdMode:onShow()
    UIManager:setDirty(self, function() return "full", self.dimen end)
    return true
end

function BirdMode:nextBird()
    self:showBird()
    -- A full (flashing) refresh each time, so no ghost of the last bird remains.
    UIManager:setDirty(self, function() return "full", self.dimen end)
    return true
end

function BirdMode:onTap() return self:nextBird() end
function BirdMode:onSwipe() return self:nextBird() end

function BirdMode:onHold(_, ges)
    if ges and ges.pos and ges.pos.y < self.dimen.h * EXIT_STRIP then
        UIManager:close(self)
    end
    return true
end

local function swallow() return true end
BirdMode.onHoldRelease = swallow
BirdMode.onPan = swallow
BirdMode.onPanRelease = swallow
BirdMode.onDoubleTap = swallow
BirdMode.onTwoFingerTap = swallow
BirdMode.onPinch = swallow
BirdMode.onSpread = swallow
BirdMode.onMultiSwipe = swallow

function BirdMode:onCloseWidget()
    if self[1] then self[1]:free() end
    UIManager:setDirty(nil, "full")
end

local BirdScreen = WidgetContainer:extend{
    name = "birdscreen",
    is_doc_only = false,
}

function BirdScreen:init()
    lfs.mkdir(DIR)
    -- Set the sleep screen once; after that, the KOReader menu is in charge.
    if not G_reader_settings:isTrue("birdscreen_configured") then
        G_reader_settings:saveSetting("screensaver_type", "random_image")
        G_reader_settings:saveSetting("screensaver_dir", DIR)
        G_reader_settings:makeTrue("birdscreen_configured")
    end
    Dispatcher:registerAction("birdmode", {
        category = "none", event = "BirdMode", title = _("Bird mode"), general = true,
    })
    self.ui.menu:registerToMainMenu(self)
end

function BirdScreen:onBirdMode()
    local files = {}
    for name in lfs.dir(DIR) do
        if name:match("%.png$") then table.insert(files, DIR .. "/" .. name) end
    end
    if #files == 0 then
        UIManager:show(InfoMessage:new{
            text = _("No birds yet. Connect to Wi-Fi and use Tools > Bird screen > Refresh now."),
        })
        return true
    end
    if not Deck.seeded then
        math.randomseed(os.time())
        Deck.seeded = true
    end
    UIManager:show(BirdMode:new{ files = files })
    return true
end

-- GET url into path (via a .part file renamed into place). Returns true, or
-- false and a reason.
local function fetch(url, path)
    local http = require("socket.http")
    local ltn12 = require("ltn12")
    local socket = require("socket")
    local socketutil = require("socketutil")

    local tmp = path .. ".part"
    local fh = io.open(tmp, "wb")
    if not fh then return false, "cannot write " .. tmp end
    socketutil:set_timeout(socketutil.FILE_BLOCK_TIMEOUT, socketutil.FILE_TOTAL_TIMEOUT)
    local code, _headers, status = socket.skip(1, http.request{
        url = url,
        method = "GET",
        sink = ltn12.sink.file(fh), -- closes fh when done
    })
    socketutil:reset_timeout()
    if code == 200 and (lfs.attributes(tmp, "size") or 0) > 0 then
        os.rename(tmp, path)
        return true
    end
    os.remove(tmp)
    logger.warn("BirdScreen:", url, "failed", code, status)
    return false, tostring(status or code)
end

local function birdFile(key)
    return DIR .. "/" .. key .. ".png"
end

-- Amazon's folder is kept by the Bird screen KUAL extension's sync script
-- (it matches birds by content, since the ScreenSavers hack renames them).
-- With the pool now current here it downloads nothing; it only updates that
-- folder. Run it in the background so the reader stays responsive.
function BirdScreen:mirrorToAmazon()
    if lfs.attributes(SYNC_SH, "mode") ~= "file" then return end
    os.execute("/bin/sh " .. SYNC_SH .. " >/dev/null 2>&1 &")
end

-- Sync the folder to the site's pool: fetch the list, download missing birds
-- one per UI tick (so the reader stays responsive), then drop the rest.
function BirdScreen:refresh(force)
    if self.busy then return end
    local last = G_reader_settings:readSetting("birdscreen_last") or 0
    if not force and os.time() - last < MIN_INTERVAL then return end

    local list = DIR .. "/.pool.json"
    local ok, err = fetch(SITE .. "kindle.json", list)
    local keys
    if ok then
        local fh = io.open(list, "r")
        local okj, data = pcall(require("json").decode, fh and fh:read("*a") or "")
        if fh then fh:close() end
        keys = okj and type(data) == "table" and data.frames
    end
    if type(keys) ~= "table" or #keys == 0 then
        if force then
            UIManager:show(InfoMessage:new{
                text = _("Bird screen: could not get the bird list (") .. tostring(err or "empty") .. ")",
                timeout = 3,
            })
        end
        return
    end

    local missing = {}
    for _i, key in ipairs(keys) do
        if lfs.attributes(birdFile(key), "mode") ~= "file" then table.insert(missing, key) end
    end

    self.busy = true
    local got, failed = 0, 0
    local function finish()
        self.busy = false
        local keep = {}
        for _i, key in ipairs(keys) do keep[key .. ".png"] = true end
        for name in lfs.dir(DIR) do
            if name:match("%.png$") and not keep[name] then os.remove(DIR .. "/" .. name) end
        end
        if failed == 0 then G_reader_settings:saveSetting("birdscreen_last", os.time()) end
        self:mirrorToAmazon()
        if force then
            UIManager:show(InfoMessage:new{
                text = failed == 0
                    and string.format(_("Bird screen: %d birds, %d new."), #keys, got)
                    or string.format(_("Bird screen: %d new, %d failed; will retry."), got, failed),
                timeout = 3,
            })
        end
    end
    local function step(n)
        if n > #missing then return finish() end
        local key = missing[n]
        if fetch(SITE .. "kindle.png?frame=" .. key, birdFile(key)) then
            got = got + 1
        else
            failed = failed + 1
        end
        UIManager:scheduleIn(0.2, function() step(n + 1) end)
    end
    step(1)
end

function BirdScreen:onNetworkConnected()
    -- Let the connection settle and the other listeners go first.
    UIManager:scheduleIn(5, function() self:refresh(false) end)
end

function BirdScreen:onResume()
    if NetworkMgr:isOnline() then
        UIManager:scheduleIn(5, function() self:refresh(false) end)
    end
end

function BirdScreen:addToMainMenu(menu_items)
    menu_items.birdmode = {
        text = _("Bird mode"),
        sorting_hint = "tools",
        keep_menu_open = false,
        callback = function() self:onBirdMode() end,
    }
    menu_items.birdscreen = {
        text = _("Bird screen"),
        sorting_hint = "tools",
        sub_item_table = {
            {
                text = _("Refresh now"),
                callback = function()
                    NetworkMgr:runWhenOnline(function() self:refresh(true) end)
                end,
            },
            {
                text = _("Use bird as sleep screen"),
                checked_func = function()
                    return G_reader_settings:readSetting("screensaver_type") == "random_image"
                        and G_reader_settings:readSetting("screensaver_dir") == DIR
                end,
                callback = function()
                    G_reader_settings:saveSetting("screensaver_type", "random_image")
                    G_reader_settings:saveSetting("screensaver_dir", DIR)
                end,
            },
        },
    }
end

return BirdScreen
