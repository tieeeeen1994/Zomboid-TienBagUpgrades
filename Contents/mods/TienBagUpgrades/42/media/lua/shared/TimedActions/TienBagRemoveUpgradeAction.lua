--[[
    Tien's Bag Upgrades - cut an upgrade off a bag and get the upgrade item back.

    Same pattern as TienBagAddUpgradeAction: complete() on the server (or single player) checks the
    bag, the cutting tool, that the bag still has that upgrade and that its contents still fit without
    it, and returns false (Reject) otherwise.
]]

require "TimedActions/ISBaseTimedAction"
require "TienBagUpgrades/TienBagUpgrades_Shared"

local TBU = TienBagUpgrades

TienBagRemoveUpgradeAction = ISBaseTimedAction:derive("TienBagRemoveUpgradeAction")

local function hasUpgrade(bag, upgradeType)
    for _, t in ipairs(TBU.getUpgrades(bag) or {}) do
        if t == upgradeType then return true end
    end
    return false
end

function TienBagRemoveUpgradeAction:isValid()
    if isClient() and self.started then return true end
    local inventory = self.character:getInventory()
    return self.bag ~= nil and self.cutter ~= nil
        and inventory:containsID(self.bag:getID())
        and inventory:containsID(self.cutter:getID())
        and TBU.isCutter(self.cutter)
        and hasUpgrade(self.bag, self.upgradeType)
        and TBU.removeCheck(self.bag, self.upgradeType)
end

function TienBagRemoveUpgradeAction:start()
    if isClient() then
        local inventory = self.character:getInventory()
        self.bag = inventory:getItemById(self.bag:getID())
        self.cutter = inventory:getItemById(self.cutter:getID())
        self.started = true
    end
    if self.bag then
        self.bag:setJobType(getText("ContextMenu_TienBagUpgrades_RemoveUpgrade"))
        self.bag:setJobDelta(0)
    end
    self:setActionAnim("SewingCloth")
end

function TienBagRemoveUpgradeAction:update()
    if self.bag then self.bag:setJobDelta(self:getJobDelta()) end
    self.character:setMetabolicTarget(Metabolics.UsingTools)
end

function TienBagRemoveUpgradeAction:stop()
    if self.bag then self.bag:setJobDelta(0) end
    self.started = false
    ISBaseTimedAction.stop(self)
end

function TienBagRemoveUpgradeAction:perform()
    if self.bag then self.bag:setJobDelta(0) end
    self.started = false
    ISBaseTimedAction.perform(self)
end

function TienBagRemoveUpgradeAction:complete()
    local bag, cutter, upgradeType = self.bag, self.cutter, self.upgradeType
    if not bag or not cutter or not TBU.UPGRADES[upgradeType] then return false end
    local inventory = self.character:getInventory()
    if not inventory:contains(bag) or not inventory:contains(cutter) or not TBU.isCutter(cutter) then return false end
    if not hasUpgrade(bag, upgradeType) or not TBU.removeCheck(bag, upgradeType) then return false end

    local list = bag:getModData().LUpgrades
    for i = 1, #list do
        if list[i] == upgradeType then
            table.remove(list, i)
            break
        end
    end
    local item = inventory:AddItem(TBU.fullType(upgradeType))
    if item then sendAddItemToContainer(inventory, item) end
    TBU.apply(bag, self.character)
    return true
end

function TienBagRemoveUpgradeAction:getDuration()
    if self.bag == nil then return 0 end
    if self.character:isTimedActionInstant() then return 1 end
    return 100 - self.character:getPerkLevel(Perks.Tailoring) * 4
end

function TienBagRemoveUpgradeAction:new(character, bag, upgradeType, cutter)
    local o = ISBaseTimedAction.new(self, character)
    o.bag = bag
    o.upgradeType = upgradeType
    o.cutter = cutter
    o.started = false
    o.maxTime = o:getDuration()
    return o
end
