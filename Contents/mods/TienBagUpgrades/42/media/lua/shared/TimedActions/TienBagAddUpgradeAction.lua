--[[
    Tien's Bag Upgrades - sew an upgrade onto a bag.

    Built like vanilla ISRepairClothing: the client checks and animates, the server (or single
    player) checks again in complete() and makes every change there. complete() returning false makes
    the server answer Reject, so nothing is used up when the bag, the upgrade or the tools are gone or
    the bag has no free slot by then. Every item must be in the main inventory (the menu queues the
    transfers first).
]]

require "TimedActions/ISBaseTimedAction"
require "TienBagUpgrades/TienBagUpgrades_Shared"

local TBU = TienBagUpgrades

TienBagAddUpgradeAction = ISBaseTimedAction:derive("TienBagAddUpgradeAction")

local function stopSound(self)
    if self.sound and self.character:getEmitter():isPlaying(self.sound) then
        self.character:stopOrTriggerSound(self.sound)
    end
    self.sound = nil
end

function TienBagAddUpgradeAction:isValid()
    if isClient() and self.started then return true end
    local inventory = self.character:getInventory()
    return self.bag ~= nil and self.upgrade ~= nil and self.needle ~= nil and self.thread ~= nil
        and inventory:containsID(self.bag:getID())
        and inventory:containsID(self.upgrade:getID())
        and inventory:containsID(self.needle:getID())
        and inventory:containsID(self.thread:getID())
        and self.thread:getCurrentUses() > 0
        and TBU.hasFreeSlot(self.bag, self.character)
end

function TienBagAddUpgradeAction:start()
    if isClient() then
        -- A transfer in multiplayer replaces the client's item objects; pick up the current ones.
        local inventory = self.character:getInventory()
        self.bag = inventory:getItemById(self.bag:getID())
        self.upgrade = inventory:getItemById(self.upgrade:getID())
        self.needle = inventory:getItemById(self.needle:getID())
        self.thread = inventory:getItemById(self.thread:getID())
        self.started = true
    end
    if self.bag then
        self.bag:setJobType(getText("ContextMenu_TienBagUpgrades_AddUpgrade"))
        self.bag:setJobDelta(0)
    end
    self:setActionAnim("SewingCloth")
    self.sound = self.character:playSound("Sewing")
end

function TienBagAddUpgradeAction:update()
    if self.bag then self.bag:setJobDelta(self:getJobDelta()) end
    self.character:setMetabolicTarget(Metabolics.UsingTools)
end

function TienBagAddUpgradeAction:stop()
    stopSound(self)
    if self.bag then self.bag:setJobDelta(0) end
    self.started = false
    ISBaseTimedAction.stop(self)
end

function TienBagAddUpgradeAction:perform()
    stopSound(self)
    if self.bag then self.bag:setJobDelta(0) end
    self.started = false
    ISBaseTimedAction.perform(self)
end

function TienBagAddUpgradeAction:complete()
    local bag, upgrade, needle, thread = self.bag, self.upgrade, self.needle, self.thread
    if not bag or not upgrade or not needle or not thread then return false end
    local inventory = self.character:getInventory()
    if not inventory:contains(bag) or not inventory:contains(upgrade) then return false end
    if not inventory:contains(needle) or not inventory:contains(thread) then return false end
    if not TBU.isBag(bag) or not TBU.upgradeInfo(upgrade) then return false end
    if thread:getCurrentUses() <= 0 or not TBU.hasFreeSlot(bag, self.character) then return false end

    local md = TBU.ensureBase(bag)
    table.insert(md.LUpgrades, upgrade:getType())
    inventory:Remove(upgrade)
    sendRemoveItemFromContainer(inventory, upgrade)
    thread:UseAndSync()
    TBU.apply(bag, self.character)
    -- Sandbox SewingXP (default 0; patching clothing gives 2). Cutting the upgrade off gives none: it always gives
    -- the item back, so a sew / cut loop costs a thread use per SewingXP.
    local xp = TBU.opt("SewingXP")
    if xp > 0 then addXp(self.character, Perks.Tailoring, xp) end
    return true
end

function TienBagAddUpgradeAction:getDuration()
    if self.bag == nil or self.upgrade == nil then return 0 end
    if self.character:isTimedActionInstant() then return 1 end
    return 150 - self.character:getPerkLevel(Perks.Tailoring) * 6
end

function TienBagAddUpgradeAction:new(character, bag, upgrade, needle, thread)
    local o = ISBaseTimedAction.new(self, character)
    o.bag = bag
    o.upgrade = upgrade
    o.needle = needle
    o.thread = thread
    o.started = false
    o.maxTime = o:getDuration()
    return o
end
