--[[--
Bird screen: starred birds from scott-ouellette.com as KOReader's sleep screen.

The site renders /birds/kindle.png?slot=N for this panel (1072x1448, 16
grays). This downloads a pool of POOL of them into its own folder and points
KOReader's "random image" sleep screen at that folder, so every sleep shows a
different bird without needing Wi-Fi. The pool is the latest POOL starred birds.

The pool refreshes when Wi-Fi connects (or on wake while online), at most
every few hours, and from Tools > Bird screen > Refresh now. A failed
download keeps that slot's previous bird.
--]]--

local DataStorage = require("datastorage")
local InfoMessage = require("ui/widget/infomessage")
local NetworkMgr = require("ui/network/manager")
local UIManager = require("ui/uimanager")
local WidgetContainer = require("ui/widget/container/widgetcontainer")
local lfs = require("libs/libkoreader-lfs")
local logger = require("logger")
local _ = require("gettext")

local URL = "https://www.scott-ouellette.com/birds/kindle.png?slot="
local DIR = DataStorage:getDataDir() .. "/birdscreen"
local POOL = 10 -- matches kindle.POOL on the site
local LINKSS = "/mnt/us/linkss/screensavers" -- Amazon's sleep screen, via the ScreenSavers hack
local MIN_INTERVAL = 3 * 3600 -- seconds between automatic refreshes

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
    self.ui.menu:registerToMainMenu(self)
end

-- Copy a bird into the ScreenSavers hack's folder (linkss), so Amazon's own
-- sleep screen shows the same pool. Amazon reads that folder at boot, so new
-- birds appear there after the next restart. Written beside the target and
-- renamed into place: a half-written PNG would stall Amazon's UI until reboot.
function BirdScreen:mirrorToAmazon(file, slot)
    if lfs.attributes(LINKSS, "mode") ~= "directory" then return end
    local src = io.open(file, "rb")
    if not src then return end
    local data = src:read("*a")
    src:close()
    local dest = string.format("%s/bird-%02d.png", LINKSS, slot)
    local out = io.open(dest .. ".part", "wb")
    if not out then return end
    out:write(data)
    out:close()
    os.rename(dest .. ".part", dest)
end

-- Download one slot. Returns true on success, or false and a reason.
function BirdScreen:download(slot)
    local http = require("socket.http")
    local ltn12 = require("ltn12")
    local socket = require("socket")
    local socketutil = require("socketutil")

    local file = string.format("%s/bird-%02d.png", DIR, slot)
    local tmp = file .. ".part"
    local fh = io.open(tmp, "wb")
    if not fh then return false, "cannot write " .. tmp end
    socketutil:set_timeout(socketutil.FILE_BLOCK_TIMEOUT, socketutil.FILE_TOTAL_TIMEOUT)
    local code, _headers, status = socket.skip(1, http.request{
        url = URL .. slot,
        method = "GET",
        sink = ltn12.sink.file(fh), -- closes fh when done
    })
    socketutil:reset_timeout()
    if code == 200 and (lfs.attributes(tmp, "size") or 0) > 1024 then
        os.rename(tmp, file)
        self:mirrorToAmazon(file, slot)
        return true
    end
    os.remove(tmp)
    logger.warn("BirdScreen: slot", slot, "failed", code, status)
    return false, tostring(status or code)
end

-- Fetch the whole pool, one slot per UI tick so the reader stays responsive.
function BirdScreen:refresh(force)
    if self.busy then return end
    local last = G_reader_settings:readSetting("birdscreen_last") or 0
    if not force and os.time() - last < MIN_INTERVAL then return end
    self.busy = true
    local got, err = 0, nil
    local function step(slot)
        local ok, why = self:download(slot)
        if ok then got = got + 1 else err = why end
        if slot + 1 < POOL then
            UIManager:scheduleIn(0.2, function() step(slot + 1) end)
            return
        end
        self.busy = false
        if got > 0 then
            G_reader_settings:saveSetting("birdscreen_last", os.time())
            os.remove(DIR .. "/bird.png") -- the single seed image from setup
        end
        if force then
            UIManager:show(InfoMessage:new{
                text = got == POOL and _("Bird screen updated.")
                    or string.format(_("Bird screen: got %d of %d birds (%s)."), got, POOL, err or "?"),
                timeout = 3,
            })
        end
    end
    step(0)
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
